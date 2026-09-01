"""Exercises the real face engine against real photographs.

Everything else in the suite uses a deterministic stand-in so tests stay fast.
This module loads the actual ONNX models and checks the property the whole
product depends on: the same person scores high, a different person scores low,
and a photo with no person in it yields nothing.

Skipped automatically when the models have not been downloaded, so a fresh
checkout still runs green:

    python -m app.face.download
    pytest tests/test_face_engine.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.config import settings

cv2 = pytest.importorskip("cv2")
pytest.importorskip("onnxruntime")

MODEL_DIR = Path(settings.face_model_dir) / settings.face_model_pack
MODELS_PRESENT = MODEL_DIR.exists() and any(MODEL_DIR.glob("*.onnx"))

pytestmark = pytest.mark.skipif(
    not MODELS_PRESENT,
    reason=f"Face models not found in {MODEL_DIR}. Run `python -m app.face.download`.",
)


@pytest.fixture(scope="module")
def engine():
    from app.face.arcface import ArcFaceEngine

    return ArcFaceEngine(
        model_dir=settings.face_model_dir,
        pack=settings.face_model_pack,
        detect_size=settings.face_detect_size,
        detect_threshold=settings.face_detect_threshold,
    )


@pytest.fixture(scope="module")
def faces() -> dict[str, np.ndarray]:
    """Two real, clearly different faces plus a non-face control.

    Sourced from image data bundled inside installed packages so the test needs
    no network access and no committed binaries.
    """
    skimage_data = pytest.importorskip("skimage.data")
    cbook = pytest.importorskip("matplotlib.cbook")
    from PIL import Image

    collins = skimage_data.astronaut()
    with cbook.get_sample_data("grace_hopper.jpg") as handle:
        hopper = np.array(Image.open(handle).convert("RGB"))
    cat = skimage_data.chelsea()

    to_bgr = lambda rgb: cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)  # noqa: E731
    return {"collins": to_bgr(collins), "hopper": to_bgr(hopper), "cat": to_bgr(cat)}


def test_detects_exactly_one_face_per_portrait(engine, faces):
    for name in ("collins", "hopper"):
        detected = engine.detect(faces[name])
        assert len(detected) == 1, f"expected one face in {name}, got {len(detected)}"
        assert detected[0].score > 0.6
        assert detected[0].box.width > 0 and detected[0].box.height > 0


def test_finds_no_face_in_a_photo_of_a_cat(engine, faces):
    assert engine.detect(faces["cat"]) == []


def test_embeddings_are_unit_length(engine, faces):
    face = engine.detect(faces["collins"])[0]
    assert face.embedding.shape == (engine.dim,)
    assert np.isclose(np.linalg.norm(face.embedding), 1.0, atol=1e-4)


def test_same_person_matches_across_a_degraded_selfie(engine, faces):
    """A phone selfie is smaller, brighter, tilted and JPEG-crushed.

    This is the realistic version of the guest flow, not a comparison of an
    image with itself.
    """
    original = faces["collins"]
    small = cv2.resize(original, (220, 220))
    brightened = cv2.convertScaleAbs(small, alpha=1.25, beta=18)
    rotation = cv2.getRotationMatrix2D((110, 110), 7, 1.0)
    tilted = cv2.warpAffine(brightened, rotation, (220, 220))
    _, buffer = cv2.imencode(".jpg", tilted, [cv2.IMWRITE_JPEG_QUALITY, 40])
    selfie = cv2.imdecode(buffer, cv2.IMREAD_COLOR)

    reference = engine.detect(original)[0].embedding
    probe = engine.detect(selfie)[0].embedding
    similarity = float(np.dot(reference, probe))

    assert similarity > settings.face_match_threshold, (
        f"same person scored {similarity:.3f}, below the "
        f"{settings.face_match_threshold} threshold"
    )


def test_different_people_do_not_match(engine, faces):
    collins = engine.detect(faces["collins"])[0].embedding
    hopper = engine.detect(faces["hopper"])[0].embedding
    similarity = float(np.dot(collins, hopper))

    assert similarity < settings.face_match_threshold
    # Well clear of the threshold, not merely under it.
    assert similarity < 0.2, f"different people scored {similarity:.3f}"


def test_finds_the_right_person_in_a_group_photo(engine, faces):
    """The actual product question: who is in this photo?"""
    height = 600
    left = faces["collins"]
    right = faces["hopper"]
    scale = lambda img: cv2.resize(  # noqa: E731
        img, (int(img.shape[1] * height / img.shape[0]), height)
    )
    group = np.hstack([scale(left), scale(right)])

    detected = engine.detect(group)
    assert len(detected) == 2, f"expected two faces in the group photo, got {len(detected)}"

    collins = engine.detect(faces["collins"])[0].embedding
    hopper = engine.detect(faces["hopper"])[0].embedding

    for face in detected:
        to_collins = float(np.dot(face.embedding, collins))
        to_hopper = float(np.dot(face.embedding, hopper))
        # Each detected face must match exactly one reference, decisively.
        assert (to_collins > settings.face_match_threshold) != (
            to_hopper > settings.face_match_threshold
        ), f"ambiguous face: collins={to_collins:.3f} hopper={to_hopper:.3f}"


def test_rejects_an_empty_image(engine):
    from app.face.base import FaceError

    with pytest.raises(FaceError):
        engine.detect(np.zeros((0, 0, 3), dtype=np.uint8))
