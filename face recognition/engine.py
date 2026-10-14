"""Face engine: SCRFD detection + ArcFace embeddings (InsightFace buffalo_l) with cosine matching."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from insightface.app import FaceAnalysis

DATA_DIR = Path(__file__).parent / "data"
EMBEDDINGS_PATH = DATA_DIR / "embeddings.npz"

FACE_APP: FaceAnalysis | None = None


def get_face_app() -> FaceAnalysis:
    global FACE_APP
    if FACE_APP is None:
        FACE_APP = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        FACE_APP.prepare(ctx_id=0, det_size=(640, 640))
    return FACE_APP


def detect_faces(frame: np.ndarray):
    return get_face_app().get(frame)


def best_face(frame: np.ndarray):
    """Largest frontal-enough face with a valid embedding."""
    faces = [f for f in detect_faces(frame) if f.embedding is not None and f.bbox is not None]
    if not faces:
        return None
    return max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))


def capture_frame_for_enroll(frame: np.ndarray):
    """Return aligned-ready crop info: (face, quality) or None."""
    face = best_face(frame)
    if face is None:
        return None
    w = frame.shape[1]
    x1, y1, x2, y2 = face.bbox
    face_w = (x2 - x1) / w
    if face_w < 0.15:  # face too small for a reliable embedding
        return None
    if face.det_score < 0.85:
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
