"""SCRFD detection + ArcFace embeddings, executed with onnxruntime.

Why this combination:

* onnxruntime and opencv-python are plain pip wheels, so `pip install` works on
  Windows with no compiler and no Visual Studio build tools. The `insightface`
  package itself needs a C toolchain, so we run its published ONNX models
  directly instead of depending on the package.
* SCRFD returns the five facial landmarks ArcFace needs for alignment, so the
  detector and recogniser fit together without a separate landmark model.
* Everything runs locally. No image ever leaves the server.

Models come from the InsightFace `buffalo_l` / `buffalo_s` packs -- see
`app.face.download`.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

import cv2
import numpy as np

from app.face.base import BoundingBox, DetectedFace, FaceError

logger = logging.getLogger(__name__)

# Canonical ArcFace landmark positions inside a 112x112 crop.
ARCFACE_DST = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float64,
)

DETECTOR_FILES = {"buffalo_l": "det_10g.onnx", "buffalo_s": "det_500m.onnx"}
RECOGNISER_FILES = {"buffalo_l": "w600k_r50.onnx", "buffalo_s": "w600k_mbf.onnx"}


def _umeyama(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """Least-squares similarity transform (scale + rotation + translation).

    Umeyama 1991. Returns a 2x3 matrix suitable for ``cv2.warpAffine``.
    """
    num, dim = src.shape
    src_mean, dst_mean = src.mean(axis=0), dst.mean(axis=0)
    src_demean, dst_demean = src - src_mean, dst - dst_mean

    A = dst_demean.T @ src_demean / num
    d = np.ones((dim,), dtype=np.float64)
    if np.linalg.det(A) < 0:
        d[dim - 1] = -1

    U, S, Vt = np.linalg.svd(A)
    rank = np.linalg.matrix_rank(A)
    if rank == 0:
        raise FaceError("Degenerate landmark configuration")
    if rank == dim - 1:
        if np.linalg.det(U) * np.linalg.det(Vt) > 0:
            R = U @ Vt
        else:
            s = d[dim - 1]
            d[dim - 1] = -1
            R = U @ np.diag(d) @ Vt
            d[dim - 1] = s
    else:
        R = U @ np.diag(d) @ Vt

    scale = (S @ d) / src_demean.var(axis=0).sum()
    T = np.eye(dim + 1, dtype=np.float64)
    T[:dim, :dim] = scale * R
    T[:dim, dim] = dst_mean - scale * R @ src_mean
    return T[:2]


def _distance2bbox(points: np.ndarray, distance: np.ndarray) -> np.ndarray:
    return np.stack(
        [
            points[:, 0] - distance[:, 0],
            points[:, 1] - distance[:, 1],
            points[:, 0] + distance[:, 2],
            points[:, 1] + distance[:, 3],
        ],
        axis=-1,
    )


def _distance2kps(points: np.ndarray, distance: np.ndarray) -> np.ndarray:
    preds = []
    for i in range(0, distance.shape[1], 2):
        preds.append(points[:, 0] + distance[:, i])
        preds.append(points[:, 1] + distance[:, i + 1])
    return np.stack(preds, axis=-1)


def _nms(dets: np.ndarray, thresh: float = 0.4) -> list[int]:
    x1, y1, x2, y2, scores = dets[:, 0], dets[:, 1], dets[:, 2], dets[:, 3], dets[:, 4]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        order = order[np.where(ovr <= thresh)[0] + 1]
    return keep


class ArcFaceEngine:
    """Detect with SCRFD, embed with ArcFace. Thread-safe."""

    name = "arcface"
    dim = 512

    # SCRFD-10G / 500M topology: 3 feature maps, 2 anchors per cell.
    _FMC = 3
    _STRIDES = (8, 16, 32)
    _NUM_ANCHORS = 2

    def __init__(
        self,
        model_dir: Path,
        pack: str = "buffalo_l",
        detect_size: int = 640,
        detect_threshold: float = 0.5,
        min_face_size: int = 32,
        nms_threshold: float = 0.4,
    ) -> None:
        import onnxruntime as ort

        det_name = DETECTOR_FILES.get(pack)
        rec_name = RECOGNISER_FILES.get(pack)
        if det_name is None or rec_name is None:
            raise FaceError(f"Unknown face model pack {pack!r}")

        base = Path(model_dir) / pack
        det_path, rec_path = base / det_name, base / rec_name
        missing = [p for p in (det_path, rec_path) if not p.exists()]
        if missing:
            raise FaceError(
                "Face models are missing: "
                + ", ".join(str(p) for p in missing)
                + ". Run `python -m app.face.download` to fetch them."
            )

        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        # Face work already runs on a worker pool; let the pool provide the
        # parallelism rather than having every session spawn its own threads.
        opts.intra_op_num_threads = max(1, (cv2.getNumberOfCPUs() or 2) // 2)
        providers = ["CPUExecutionProvider"]

        self._det = ort.InferenceSession(str(det_path), opts, providers=providers)
        self._rec = ort.InferenceSession(str(rec_path), opts, providers=providers)
        self._det_in = self._det.get_inputs()[0].name
        self._det_out = [o.name for o in self._det.get_outputs()]
        self._rec_in = self._rec.get_inputs()[0].name
        self._rec_out = self._rec.get_outputs()[0].name
        self.dim = int(self._rec.get_outputs()[0].shape[-1])

        self.detect_size = (detect_size, detect_size)
        self.detect_threshold = detect_threshold
        self.min_face_size = min_face_size
        self.nms_threshold = nms_threshold
        self._lock = threading.Lock()
        logger.info("ArcFace engine ready (pack=%s, dim=%d)", pack, self.dim)

    # -- detection ---------------------------------------------------------
    def _run_detector(self, image_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        h, w = image_bgr.shape[:2]
        target_w, target_h = self.detect_size
        # Letterbox into the square input, preserving aspect ratio.
        if h / w > target_h / target_w:
            new_h, new_w = target_h, max(1, int(target_h * w / h))
        else:
            new_w, new_h = target_w, max(1, int(target_w * h / w))
        scale = new_h / h

        canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
        canvas[:new_h, :new_w] = cv2.resize(image_bgr, (new_w, new_h))
        blob = cv2.dnn.blobFromImage(
            canvas, 1.0 / 128, self.detect_size, (127.5, 127.5, 127.5), swapRB=True
        )

        with self._lock:
            outs = self._det.run(self._det_out, {self._det_in: blob})

        all_scores, all_boxes, all_kps = [], [], []
        for idx, stride in enumerate(self._STRIDES):
            scores = outs[idx].ravel()
            keep = np.where(scores >= self.detect_threshold)[0]
            if keep.size == 0:
                continue
            bbox_preds = outs[idx + self._FMC] * stride
            kps_preds = outs[idx + self._FMC * 2] * stride

            fh, fw = target_h // stride, target_w // stride
            gx, gy = np.meshgrid(np.arange(fw), np.arange(fh))
            centers = (np.stack([gx, gy], axis=-1).astype(np.float32) * stride).reshape(-1, 2)
            if self._NUM_ANCHORS > 1:
                centers = np.stack([centers] * self._NUM_ANCHORS, axis=1).reshape(-1, 2)

            all_scores.append(scores[keep])
            all_boxes.append(_distance2bbox(centers, bbox_preds)[keep])
            all_kps.append(_distance2kps(centers, kps_preds)[keep].reshape(-1, 5, 2))

        if not all_scores:
            return np.zeros((0, 5), np.float32), np.zeros((0, 5, 2), np.float32)

        scores = np.concatenate(all_scores)
        boxes = np.concatenate(all_boxes) / scale
        kpss = np.concatenate(all_kps) / scale

        order = scores.argsort()[::-1]
        dets = np.hstack([boxes, scores[:, None]]).astype(np.float32)[order]
        keep = _nms(dets, self.nms_threshold)
        return dets[keep], kpss[order][keep]

    # -- embedding ---------------------------------------------------------
    def _embed(self, image_bgr: np.ndarray, landmarks: np.ndarray) -> np.ndarray:
        matrix = _umeyama(np.asarray(landmarks, dtype=np.float64), ARCFACE_DST)
        aligned = cv2.warpAffine(image_bgr, matrix, (112, 112), borderValue=0.0)
        blob = cv2.dnn.blobFromImage(
            aligned, 1.0 / 127.5, (112, 112), (127.5, 127.5, 127.5), swapRB=True
        )
        with self._lock:
            vec = self._rec.run([self._rec_out], {self._rec_in: blob})[0][0]
        norm = np.linalg.norm(vec)
        if norm == 0:
            raise FaceError("Recogniser produced a zero vector")
        return (vec / norm).astype(np.float32)

    # -- public ------------------------------------------------------------
    def detect(self, image_bgr: np.ndarray) -> list[DetectedFace]:
        if image_bgr is None or image_bgr.size == 0:
            raise FaceError("Empty image")
        if image_bgr.ndim == 2:
            image_bgr = cv2.cvtColor(image_bgr, cv2.COLOR_GRAY2BGR)

        dets, kpss = self._run_detector(image_bgr)
        h, w = image_bgr.shape[:2]
        faces: list[DetectedFace] = []

        for det, kps in zip(dets, kpss):
            x1, y1, x2, y2, score = det
            bw, bh = int(round(x2 - x1)), int(round(y2 - y1))
            # Skip faces too small to embed reliably -- background crowds
            # otherwise generate noisy vectors that pollute search results.
            if min(bw, bh) < self.min_face_size:
                continue
            faces.append(
                DetectedFace(
                    box=BoundingBox(
                        x=max(0, int(round(x1))),
                        y=max(0, int(round(y1))),
                        width=min(bw, w),
                        height=min(bh, h),
                    ),
                    score=float(score),
                    embedding=self._embed(image_bgr, kps),
                )
            )
        return faces
