"""Face engine: SCRFD detection + ArcFace embeddings (InsightFace buffalo_l) with cosine matching."""
from __future__ import annotations

import json
import threading
from pathlib import Path

import cv2
import numpy as np
from insightface.app import FaceAnalysis

DATA_DIR = Path(__file__).parent / "data"
EMBEDDINGS_PATH = DATA_DIR / "embeddings.npz"

FACE_APP: FaceAnalysis | None = None
_APP_LOCK = threading.RLock()      # استنتاج ONNX هم‌زمان از چند رشته امن نیست


def get_face_app() -> FaceAnalysis:
    global FACE_APP
    if FACE_APP is None:
        with _APP_LOCK:
            if FACE_APP is None:
                app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
                app.prepare(ctx_id=0, det_size=(640, 640))
                FACE_APP = app
    return FACE_APP


def detect_faces(frame: np.ndarray):
    """اینفرانس سریال‌شده: داشبورد و مانیتور هم‌زمان مدل را درگیر نمی‌کنند."""
    with _APP_LOCK:
        return get_face_app().get(frame)


MIN_FACE_RATIO = 0.15   # عرض چهره نسبت به عرض تصویر، کمتر از آن بردار قابل اتکا نیست
MIN_DET_SCORE = 0.75    # چهره تمام‌رخ در عکس ۷۲۰px حدود ۰.۸۸ می‌گیرد؛ زیر این مقدار پروفیل/تار است


def _largest_face(frame: np.ndarray):
    faces = [f for f in detect_faces(frame) if f.embedding is not None and f.bbox is not None]
    if not faces:
        return None
    return max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))


def best_face(frame: np.ndarray):
    """Largest face with a valid embedding."""
    return _largest_face(frame)


def _grade(face, frame) -> str:
    if (face.bbox[2] - face.bbox[0]) / max(frame.shape[1], 1) < MIN_FACE_RATIO:
        return "small"
    if face.det_score < MIN_DET_SCORE:
        return "weak"
    return "ok"


def face_quality(frame: np.ndarray) -> tuple[str, float]:
    """چراغ‌راهنمای کیفیت عکس: ('ok'|'noface'|'small'|'weak', det_score)."""
    face = _largest_face(frame)
    if face is None:
        return "noface", 0.0
    return _grade(face, frame), float(face.det_score)


def _pose(face) -> tuple[float, float]:
    """زاویه سر از پنج نقطه چهره: (yaw, pitch) نرمال‌شده با فاصله چشم‌ها.

    yaw صفر یعنی تمام‌رخ؛ چرخش سر علامت را عوض می‌کند. pitch هم همین‌طور.
    قدر مطلق‌ها واحد دلخواه‌اند، بنابراین مقایسه با خط‌مبدأ (حالت تمام‌رخ)
    معنا دارد، نه مقدار مطلق — همین باعث می‌شود جای دوربین روی نتیجه اثر نگذارد.
    """
    kps = getattr(face, "kps", None)
    if kps is None or len(kps) < 5:
        return 0.0, 0.0
    le, re, nose = np.asarray(kps[0], float), np.asarray(kps[1], float), np.asarray(kps[2], float)
    eye_mid = (le + re) / 2
    eye_dist = float(np.linalg.norm(le - re)) or 1.0
    return (float((nose[0] - eye_mid[0]) / eye_dist), float((nose[1] - eye_mid[1]) / eye_dist))


def analyze(frame: np.ndarray) -> dict:
    """کیفیت + زاویه سر؛ برای راهنمایی مرحله‌به‌مرحله «احراز هویت با وب‌کم»."""
    face = _largest_face(frame)
    if face is None:
        return {"reason": "noface", "det": 0.0, "yaw": 0.0, "pitch": 0.0}
    yaw, pitch = _pose(face)
    return {"reason": _grade(face, frame), "det": float(face.det_score),
            "yaw": yaw, "pitch": pitch}


def identify(frame: np.ndarray, threshold: float) -> dict:
    """یک عکس -> کیفیت چهره + نزدیک‌ترین دانشجو در گالری (بخش «تست تشخیص چهره»)."""
    face = _largest_face(frame)
    if face is None:
        return {"reason": "noface", "det": 0.0, "best_id": None, "best_sim": 0.0,
                "student_id": None}
    gallery, ids = load_gallery()
    best_id = best_sim = None
    if gallery.size:
        q = face.embedding / np.linalg.norm(face.embedding)
        g = gallery / (np.linalg.norm(gallery, axis=1, keepdims=True) + 1e-8)
        sims = g @ q
        i = int(np.argmax(sims))
        best_id, best_sim = int(ids[i]), float(sims[i])
    return {
        "reason": _grade(face, frame),
        "det": float(face.det_score),
        "best_id": best_id,
        "best_sim": best_sim or 0.0,
        "student_id": best_id if (best_sim or 0.0) >= threshold else None,
    }


def capture_frame_for_enroll(frame: np.ndarray):
    """بزرگ‌ترین چهره قابل استفاده، یا None."""
    face = _largest_face(frame)
    if face is None or _grade(face, frame) != "ok":
        return None
    return face


def load_gallery() -> tuple[np.ndarray, list[int]]:
    """Return (embedding matrix N x 512, list of student_ids)."""
    if not EMBEDDINGS_PATH.exists():
        return np.empty((0, 512), dtype=np.float32), []
    with np.load(EMBEDDINGS_PATH) as data:
        return data["embeddings"], list(data["student_ids"])


def add_embeddings(student_id: int, embeddings: list[np.ndarray]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    emb, ids = load_gallery()
    new = np.asarray(embeddings, dtype=np.float32)
    emb = np.vstack([emb, new]) if emb.size else new
    ids = ids + [student_id] * len(embeddings)
    np.savez_compressed(EMBEDDINGS_PATH, embeddings=emb, student_ids=np.asarray(ids, dtype=np.int64))


def remove_student(student_id: int) -> int:
    emb, ids = load_gallery()
    if emb.size == 0:
        return 0
    ids = np.asarray(ids)
    keep = ids != student_id
    removed = int((~keep).sum())
    np.savez_compressed(
        EMBEDDINGS_PATH,
        embeddings=emb[keep],
        student_ids=ids[keep],
    )
    return removed


def match(embedding: np.ndarray, threshold: float) -> tuple[int | None, float]:
    """Cosine similarity against the whole gallery; returns best (student_id, score)."""
    emb, ids = load_gallery()
    if emb.size == 0:
        return None, 0.0
    q = embedding / np.linalg.norm(embedding)
    g = emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-8)
    sims = g @ q
    best = int(np.argmax(sims))
    score = float(sims[best])
    if score >= threshold:
        return int(ids[best]), score
    return None, score


def open_camera(index: int = 0, width: int = 1280, height: int = 720) -> cv2.VideoCapture:
    for api in (cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY):
        cap = cv2.VideoCapture(index, api)
        if cap.isOpened():
            ok, frame = cap.read()
            if ok:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                return cap
        cap.release()
    raise RuntimeError(
        f"دوربین با ایندکس {index} باز نشد.\n"
        "بررسی کنید: 1) وب‌کم در Device Manager فعال باشد 2) Settings > Privacy & Security > Camera "
        "برای Desktop app apps مجاز باشد 3) ایندکس دیگر را امتحان کنید: --camera 1"
    )
