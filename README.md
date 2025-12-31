# EyeofForest

EyeofForest is a backend service for forest fire and smoke detection, refactored into a FastAPI application. The system is designed to support detection (model integration possible), drone behavior (placeholder SDK provided), and notification (email/SMS) modules.

Overview
- API is implemented under `src/api` using FastAPI.
- Modular services include detection, drone control (placeholder), and notifications.
- Database: SQLite (default path `data/auth.db`).
- Large model file is kept in the repository at `backup/yolov4.weights` (you may replace this with external storage or Git LFS).

Quick start

1. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate   # on Windows PowerShell
pip install -r requirements.txt
```

2. (Optional) Configure environment variables using a `.env` file:

```
DB_PATH=data/auth.db
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=you@example.com
SMTP_PASS=secret
SMS_API_URL=https://sms.example/api
SMS_API_KEY=xxxx
```

3. Run the application:

```bash
python -m uvicorn src.api:app --reload
```

Main API endpoints
- `GET /health` — health check
- `POST /detect` — upload an image using form-data field `file`; runs detection (currently a placeholder). If fire/smoke is detected the drone behavior is triggered and stored contacts are notified.
- `POST /contacts` — create a contact
- `GET /contacts` — list contacts
- `DELETE /contacts/{id}` — delete a contact

Notes and next steps
- `src/api/services/detection.py` is a placeholder for detection logic; integrate your model here when ready.
- `src/api/services/drone_control.py` contains placeholder drone-control methods; integrate a real drone SDK (e.g. MAVSDK, DJI SDK) for actual flight commands.
- For large model files consider using Git LFS or external storage; the repo currently keeps `backup/yolov4.weights`.

Files and locations
- API: `src/api`
- DB: `data/auth.db`
- Model: `backup/yolov4.weights`

Frontend (web UI)
 - The web UI is under `src/frontend` and served by the FastAPI app's static files.
 - New features added:
	 - Responsive navbar with hover dropdowns and a mobile hamburger menu.
	 - Client-side hash routing for pages: `#home`, `#live`, `#recordings`, `#settings`, `#advanced`, `#about`.
	 - Live camera streaming via WebSocket endpoint `/ws/stream` (server reads camera with OpenCV and streams JPEG frames).
	 - Overlay drawing improved (devicePixelRatio aware) and smoke ('duman') filled-boxes disabled to avoid large yellow boxes.

Running the UI
1. Start the backend server (serves the UI at `/`):

```powershell
py -3.10 -m uvicorn src.api:app --reload
```

2. Open the UI: http://127.0.0.1:8000/ and use the navbar to switch pages. On mobile, use the ☰ button to open the menu.

Notes
 - If you want the old `styles.css` replaced permanently, the current `styles.css` in `src/frontend` is the cleaned version.
 - The recordings/settings pages are placeholders and can be wired to backend APIs if desired.