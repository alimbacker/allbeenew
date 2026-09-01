"""QR code rendering for event links."""

from __future__ import annotations

import io

import qrcode
from qrcode.constants import ERROR_CORRECT_Q

from app.config import settings


def event_qr_png(event_code: str, box_size: int = 12, border: int = 3) -> bytes:
    """Render the public event URL as a PNG.

    Error correction level Q tolerates roughly 25% damage, which matters when
    the code is printed on a table card that gets handled all evening.
    """
    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_Q, box_size=box_size, border=border)
    qr.add_data(settings.event_url(event_code))
    qr.make(fit=True)
    img = qr.make_image(fill_color="#111111", back_color="#FFFFFF").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
