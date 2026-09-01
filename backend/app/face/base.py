"""Face engine interface.

Everything above this layer deals in ``DetectedFace`` objects and unit-length
embeddings. Swapping ArcFace for another model is a config change, not a
refactor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


class FaceError(Exception):
    """Raised when the engine cannot be used at all (missing model, bad image)."""


@dataclass(slots=True)
class BoundingBox:
    x: int
    y: int
    width: int
    height: int

    def as_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


@dataclass(slots=True)
class DetectedFace:
    box: BoundingBox
    score: float
    embedding: np.ndarray  # L2-normalised, float32

    @property
    def area(self) -> int:
        return self.box.width * self.box.height


class FaceEngine(Protocol):
    """Detect faces and turn them into comparable vectors."""

    name: str
    dim: int

    def detect(self, image_bgr: np.ndarray) -> list[DetectedFace]:
        """Return every face found, each with a unit-length embedding."""
        ...


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity for vectors that are already L2-normalised."""
    return float(np.dot(a, b))
