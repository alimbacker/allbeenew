"""Image validation, thumbnailing and decoding."""

from __future__ import annotations

import io
import logging

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import settings

logger = logging.getLogger(__name__)

# Pillow refuses very large images by default to limit decompression bombs.
# Event photography legitimately produces big files, so raise it deliberately
# rather than disabling the guard entirely.
Image.MAX_IMAGE_PIXELS = 200_000_000

PIL_FORMAT_TO_EXT = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "MPO": "jpg"}


class InvalidImageError(ValueError):
    """The uploaded bytes are not a usable image of an allowed type."""


def inspect(data: bytes) -> tuple[str, int, int]:
    """Validate image bytes by decoding them. Returns (ext, width, height).

    Content is checked by actually parsing the file, not by trusting the
    client-supplied filename or Content-Type.
    """
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
        with Image.open(io.BytesIO(data)) as img:
            fmt = (img.format or "").upper()
            width, height = img.size
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise InvalidImageError("File is not a readable image") from exc

    ext = PIL_FORMAT_TO_EXT.get(fmt)
    if ext is None or ext not in settings.extensions:
        allowed = ", ".join(sorted(settings.extensions))
        raise InvalidImageError(f"Unsupported image type {fmt or 'unknown'}. Allowed: {allowed}")
    if width < 1 or height < 1:
        raise InvalidImageError("Image has no pixels")
    return ext, width, height


def make_thumbnail(data: bytes, max_edge: int | None = None, quality: int | None = None) -> bytes:
    """Produce a WEBP thumbnail that fits inside a max_edge box.

    EXIF orientation is applied so portrait photos from a camera are not shown
    sideways in the gallery.
    """
    max_edge = max_edge or settings.thumbnail_max_edge
    quality = quality or settings.thumbnail_quality
    with Image.open(io.BytesIO(data)) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="WEBP", quality=quality, method=4)
        return out.getvalue()


def decode_bgr(data: bytes, max_edge: int = 1920) -> np.ndarray:
    """Decode to an OpenCV BGR array for face work.

    Downscales very large photos first: a 45-megapixel raw export gains nothing
    at detection time and costs a lot of memory when thousands are queued.
    """
    with Image.open(io.BytesIO(data)) as img:
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        if max(img.size) > max_edge:
            img.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        rgb = np.asarray(img)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def scale_box(box: dict, from_size: tuple[int, int], to_size: tuple[int, int]) -> dict:
    """Rescale a bounding box detected on a resized copy back to the original."""
    fw, fh = from_size
    tw, th = to_size
    if fw == 0 or fh == 0:
        return box
    sx, sy = tw / fw, th / fh
    return {
        "x": int(box["x"] * sx),
        "y": int(box["y"] * sy),
        "width": int(box["width"] * sx),
        "height": int(box["height"] * sy),
    }
