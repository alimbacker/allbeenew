"""Lazily-built process-wide face engine singleton."""

from __future__ import annotations

import logging
import threading

from app.config import settings
from app.face.base import FaceEngine, FaceError

logger = logging.getLogger(__name__)

_engine: FaceEngine | None = None
_lock = threading.Lock()


def build_engine() -> FaceEngine:
    """Construct the engine named by FACE_ENGINE."""
    if settings.face_engine == "opencv":
        from app.face.opencv_engine import OpenCVFaceEngine

        return OpenCVFaceEngine(
            model_dir=settings.face_model_dir,
            detect_size=settings.face_detect_size,
            detect_threshold=settings.face_detect_threshold,
            min_face_size=settings.face_min_size,
        )
    if settings.face_engine == "arcface":
        from app.face.arcface import ArcFaceEngine

        return ArcFaceEngine(
            model_dir=settings.face_model_dir,
            pack=settings.face_model_pack,
            detect_size=settings.face_detect_size,
            detect_threshold=settings.face_detect_threshold,
            min_face_size=settings.face_min_size,
        )
    raise FaceError(f"Unknown FACE_ENGINE {settings.face_engine!r} (expected 'arcface' or 'opencv')")


def get_engine() -> FaceEngine:
    """Return the shared engine, loading models on first use."""
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                _engine = build_engine()
    return _engine


def set_engine(engine: FaceEngine | None) -> None:
    """Swap the engine. Used by the test suite and by warm-up on startup."""
    global _engine
    with _lock:
        _engine = engine


def engine_status() -> dict:
    """Health-check payload; never raises."""
    try:
        eng = get_engine()
        return {"engine": eng.name, "dim": eng.dim, "loaded": True, "error": None}
    except Exception as exc:  # noqa: BLE001 - surfaced to /health
        return {
            "engine": settings.face_engine,
            "dim": settings.embedding_dim,
            "loaded": False,
            "error": str(exc),
        }
