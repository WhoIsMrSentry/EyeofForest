import cv2
import numpy as np
from typing import List, Dict
from pathlib import Path


# Attempt to load a YOLO model from backup/ if present. If loading fails,
# fall back to the heuristic color/contour detector implemented below.
_BASE = Path(__file__).resolve().parents[2]
_BACKUP = _BASE / "backup"
_YOLO_WEIGHT = _BACKUP / "yolov4.weights"
_YOLO_CFG = _BACKUP / "yolov4.cfg"
_COCO_NAMES = _BACKUP / "coco.names"

model_loaded = False
model = None
class_names = []
try:
    if _YOLO_WEIGHT.exists() and _YOLO_CFG.exists():
        net = cv2.dnn.readNet(str(_YOLO_WEIGHT), str(_YOLO_CFG))
        try:
            net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
            net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
        except Exception:
            pass
        model = cv2.dnn_DetectionModel(net)
        model.setInputParams(size=(416, 416), scale=1/255.0, swapRB=True)
        # default thresholds; can be tuned
        DET_CONF = 0.45
        DET_NMS = 0.4
        model_loaded = True
        if _COCO_NAMES.exists():
            with open(str(_COCO_NAMES), "r", encoding="utf-8") as f:
                class_names = [c.strip() for c in f.readlines()]
except Exception:
    model_loaded = False


def detect_in_image_bytes(image_bytes: bytes) -> List[Dict]:
    """Decode bytes and run `detect_frame` on the image."""
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return []
    return detect_frame(img)


def _find_contours_mask(mask: np.ndarray, min_area: int = 500) -> List[tuple]:
    """Return bounding boxes for contours in mask with area > min_area."""
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(c)
        boxes.append((x, y, w, h, area))
    return boxes


def detect_frame(frame: np.ndarray) -> List[Dict]:
    """Simple heuristic detection for fire (ates) and smoke (duman).

    - Fire: detect warm-colored regions in HSV (reds/oranges/yellows).
    - Smoke: detect low-saturation, light/gray regions.

    Returns list of detections like {"label":"ates","score":0.9,"box":(x,y,w,h)}
    """
    h, w = frame.shape[:2]
    results: List[Dict] = []

    # If we have a loaded YOLO model, prefer it for robust detections.
    if model_loaded and model is not None:
        try:
            classes, scores, boxes = model.detect(frame, 0.45, 0.4)
            for cls, score, box in zip(classes, scores, boxes):
                idx = int(cls[0]) if hasattr(cls, '__len__') else int(cls)
                label = class_names[idx] if idx < len(class_names) else str(idx)
                x, y, bw, bh = int(box[0]), int(box[1]), int(box[2]), int(box[3])
                results.append({"label": label, "score": float(round(float(score[0]) if hasattr(score, '__len__') else float(score), 2)), "box": (x, y, bw, bh)})
            return results
        except Exception:
            # fallback to heuristic below
            pass

    # --- Fire (orange/red/yellow) ---
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    # red/orange ranges (two ranges to capture wrap-around red)
    lower1 = np.array([0, 100, 150])
    upper1 = np.array([35, 255, 255])
    mask1 = cv2.inRange(hsv, lower1, upper1)

    # optionally include very red hues
    lower2 = np.array([170, 80, 120])
    upper2 = np.array([179, 255, 255])
    mask2 = cv2.inRange(hsv, lower2, upper2)

    fire_mask = cv2.bitwise_or(mask1, mask2)
    fire_boxes = _find_contours_mask(fire_mask, min_area=max(400, int(w * h * 0.0005)))
    for (x, y, bw, bh, area) in fire_boxes:
        # score proportional to area and mean brightness
        roi = frame[y : y + bh, x : x + bw]
        mean_v = float(np.mean(cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)[:, :, 2]))
        score = float(min(0.99, 0.3 + (area / (w * h)) * 10 + (mean_v / 255.0) * 0.5))
        results.append({"label": "ates", "score": round(score, 2), "box": (x, y, bw, bh)})

    # --- Smoke (low saturation, lighter gray regions) ---
    # convert to HSV and create mask for low saturation and medium-high brightness
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    smoke_mask = cv2.inRange(hsv, np.array([0, 0, 80]), np.array([179, 90, 230]))
    # remove bright/non-gray colors by excluding high-saturation areas
    smoke_mask = cv2.bitwise_and(smoke_mask, cv2.bitwise_not(cv2.inRange(sat, 100, 255)))
    smoke_boxes = _find_contours_mask(smoke_mask, min_area=max(800, int(w * h * 0.001)))
    for (x, y, bw, bh, area) in smoke_boxes:
        roi = frame[y : y + bh, x : x + bw]
        mean_v = float(np.mean(cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)[:, :, 2]))
        score = float(min(0.95, 0.2 + (area / (w * h)) * 8 + (1 - (np.mean(cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)[:, :, 1]) / 255.0)) * 0.4))
        results.append({"label": "duman", "score": round(score, 2), "box": (x, y, bw, bh)})

    return results
