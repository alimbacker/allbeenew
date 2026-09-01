"""YuNet detection + SFace embeddings using only OpenCV's bundled DNN wrappers.

An alternative to the ArcFace engine for constrained servers: the two model
files total ~39 MB instead of ~190 MB, and inference is noticeably cheaper.
Accuracy is lower, so the match threshold needs to be lower too -- see
docs/FACE_RECOGNITION.md.

Enable with FACE_ENGINE=opencv.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

import cv2
import numpy as np

from app.face.base import BoundingBox, DetectedFace, FaceError

logger = logging.getLogger(__name__)

DETECTOR_FILE = "face_detection_yunet_2023mar.onnx"
RECOGNISER_FILE = "face_recognition_sface_2021dec.onnx"


class OpenCVFaceEngine:
    name = "opencv"
    dim = 128

    def __init__(
        self,
        model_dir: Path,
        detect_size: int = 640,
        detect_threshold: float = 0.6,
        min_face_size: int = 32,
    ) -> None:
        base = Path(model_dir) / "opencv"
        det_path, rec_path = base / DETECTOR_FILE, base / RECOGNISER_FILE
        missing = [p for p in (det_path, rec_path) if not p.exists()]
        if missing:
            raise FaceError(
                "Face models are missing: "
                + ", ".join(str(p) for p in missing)
                + ". Run `python -m app.face.download --engine opencv` to fetch them."
            )

        self._detector = cv2.FaceDetectorYN.create(
            str(det_path), "", (detect_size, detect_size), detect_threshold, 0.3, 5000
        )
        self._recogniser = cv2.FaceRecognizerSF.create(str(rec_path), "")
        self.min_face_size = min_face_size
        self._lock = threading.Lock()
        logger.info("OpenCV YuNet/SFace engine ready")

    def detect(self, image_bgr: np.ndarray) -> list[DetectedFace]:
        if image_bgr is None or image_bgr.size == 0:
            raise FaceError("Empty image")
        if image_bgr.ndim == 2:
            image_bgr = cv2.cvtColor(image_bgr, cv2.COLOR_GRAY2BGR)

        h, w = image_bgr.shape[:2]
        with self._lock:
            self._detector.setInputSize((w, h))
            _, raw = self._detector.detect(image_bgr)
            if raw is None:
                return []
            faces: list[DetectedFace] = []
            for row in raw:
                x, y, bw, bh = (int(round(v)) for v in row[:4])
                if min(bw, bh) < self.min_face_size:
                    continue
                aligned = self._recogniser.alignCrop(image_bgr, row)
                vec = self._recogniser.feature(aligned).flatten().astype(np.float32)
                norm = np.linalg.norm(vec)
                if norm == 0:
                    continue
                faces.append(
                    DetectedFace(
                        box=BoundingBox(max(0, x), max(0, y), min(bw, w), min(bh, h)),
                        score=float(row[-1]),
                        embedding=vec / norm,
                    )
                )
        return faces
