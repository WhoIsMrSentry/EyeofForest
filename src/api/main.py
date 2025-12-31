from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import text
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from . import config
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from . import db as _db
from .models import Contact
from .schemas import Contact, ContactCreate
from .services import detection, drone_control, notifications
from .db import get_db, engine
from .db import Base
import shutil
import io
from collections import deque
import numpy as np
import base64

app = FastAPI(title="EyeofForest API")

security = HTTPBasic()


def _require_auth(credentials: HTTPBasicCredentials = Depends(security)):
    # If no password set, allow access
    if not config.FRONT_PASSWORD:
        return True
    if not credentials or credentials.password != config.FRONT_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

# mount frontend static files
app.mount("/static", StaticFiles(directory="src/frontend"), name="static")


@app.on_event("startup")
def startup():
    # create DB tables
    Base.metadata.create_all(bind=engine)
    app.state.drone = drone_control.DroneController()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/db_check")
def db_check():
    try:
        # list one table to confirm DB reachable
        with engine.connect() as conn:
            res = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' LIMIT 5"))
            tables = [r[0] for r in res]
        return {"ok": True, "db_path": config.DB_PATH, "tables": tables}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)})


@app.get("/")
def index(auth: bool = Depends(_require_auth)):
    try:
        with open("src/frontend/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except Exception:
        return HTMLResponse("<html><body><h1>EyeofForest</h1><p>No frontend available.</p></body></html>")
    


@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        stream_url = data.get("url")
        auth = data.get("auth")
        # If a frontend password is configured, require it either in the initial payload
        # or accept HTTP Basic Authorization header (Basic base64(user:pass)).
        if config.FRONT_PASSWORD:
            ok = False
            if auth and auth == config.FRONT_PASSWORD:
                ok = True
            # try Authorization header (Basic)
            if not ok:
                auth_header = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
                if auth_header and auth_header.lower().startswith("basic "):
                    try:
                        token = auth_header.split(" ", 1)[1]
                        decoded = base64.b64decode(token).decode("utf-8")
                        # form is username:password
                        parts = decoded.split(":", 1)
                        if len(parts) == 2 and parts[1] == config.FRONT_PASSWORD:
                            ok = True
                    except Exception:
                        ok = False
            if not ok:
                await websocket.send_json({"error": "unauthorized"})
                await websocket.close()
                return
        if not stream_url:
            stream_url = 0

        import cv2
        cap = cv2.VideoCapture(stream_url)
        if not cap.isOpened():
            await websocket.send_json({"error": "cannot open stream"})
            await websocket.close()
            return
        # temporal filtering buffers: keep last N masks for fire and smoke
        buffer_len = 5
        min_persist = 3
        fire_buf = deque(maxlen=buffer_len)
        smoke_buf = deque(maxlen=buffer_len)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            h, w = frame.shape[:2]
            # per-frame binary masks
            fire_mask = np.zeros((h, w), dtype=np.uint8)
            smoke_mask = np.zeros((h, w), dtype=np.uint8)

            dets = detection.detect_frame(frame)
            for d in dets:
                bbox = d.get("box")
                label = d.get("label")
                score = d.get("score", 0)
                if not bbox:
                    continue
                x, y, bw, bh = bbox
                # ignore extremely small boxes
                if bw * bh < max(500, int(w * h * 0.0003)):
                    continue
                if label == "ates":
                    cv2.rectangle(frame, (x, y), (x + bw, y + bh), (0, 0, 255), 1)
                    fire_mask[y : y + bh, x : x + bw] = 1
                elif label == "duman":
                    cv2.rectangle(frame, (x, y), (x + bw, y + bh), (200, 200, 50), 1)
                    smoke_mask[y : y + bh, x : x + bw] = 1

            # push masks into buffers
            fire_buf.append(fire_mask)
            smoke_buf.append(smoke_mask)

            # compute persistence (sum of recent masks)
            detections_meta = []
            if len(fire_buf) >= min_persist:
                acc_fire = np.sum(np.stack(list(fire_buf)), axis=0)
                persistent_fire = (acc_fire >= min_persist).astype(np.uint8)
                # draw persistent fire boxes
                contours, _ = cv2.findContours(persistent_fire, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                for c in contours:
                    x, y, bw, bh = cv2.boundingRect(c)
                    if bw * bh < max(800, int(w * h * 0.0005)):
                        continue
                    cv2.rectangle(frame, (x, y), (x + bw, y + bh), (0, 0, 255), 2)
                    cv2.putText(frame, f"ates", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 200), 2)
                    detections_meta.append({"label": "ates", "score": None, "box": [int(x), int(y), int(bw), int(bh)]})

            if len(smoke_buf) >= min_persist:
                acc_smoke = np.sum(np.stack(list(smoke_buf)), axis=0)
                persistent_smoke = (acc_smoke >= min_persist).astype(np.uint8)
                contours, _ = cv2.findContours(persistent_smoke, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                for c in contours:
                    x, y, bw, bh = cv2.boundingRect(c)
                    if bw * bh < max(1000, int(w * h * 0.0008)):
                        continue
                    cv2.rectangle(frame, (x, y), (x + bw, y + bh), (200, 200, 50), 2)
                    cv2.putText(frame, f"duman", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 50), 2)
                    detections_meta.append({"label": "duman", "score": None, "box": [int(x), int(y), int(bw), int(bh)]})

            # send metadata first (client can draw overlay based on this)
            try:
                await websocket.send_json({"type": "detections", "frame_size": [w, h], "detections": detections_meta})
            except Exception:
                pass

            _, buf = cv2.imencode('.jpg', frame)
            await websocket.send_bytes(buf.tobytes())

    except WebSocketDisconnect:
        return
    except Exception:
        await websocket.close()


@app.post("/detect")
async def detect(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    detections = detection.detect_in_image_bytes(content)
    if not detections:
        return JSONResponse({"detections": []})

    # if fire detected, instruct drone to approach and notify contacts
    for det in detections:
        if det.get("label") in ("ates", "duman"):
            # simple behavior: takeoff, start motor, go to placeholder coords, notify
            drone = app.state.drone
            drone.takeoff()
            drone.start_motor()
            # placeholder coordinates; in real system use GPS from detection
            drone.goto(0.0, 0.0, 50.0)

            # notify all contacts in DB
            contacts = db.query(Contact).all()
            for c in contacts:
                if c.email:
                    notifications.send_email(c.email, "Ateş/Duman Tespit Edildi", f"Tespit: {det}")
                if c.phone:
                    notifications.send_sms(c.phone, f"Tespit: {det}")

            drone.land()
    return {"detections": detections}


@app.post("/contacts", response_model=Yetkili)
def create_contact(contact: ContactCreate, db: Session = Depends(get_db), auth: bool = Depends(_require_auth)):
    db_item = Contact(**contact.dict())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@app.get("/contacts", response_model=list[Yetkili])
def list_contacts(db: Session = Depends(get_db), auth: bool = Depends(_require_auth)):
    return db.query(Contact).all()


@app.delete("/contacts/{contact_id}")
def delete_contact(contact_id: int, db: Session = Depends(get_db), auth: bool = Depends(_require_auth)):
    item = db.query(Contact).filter(Contact.id == contact_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(item)
    db.commit()
    return {"ok": True}
