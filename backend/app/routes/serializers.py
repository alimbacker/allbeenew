"""Turn ORM rows into API payloads.

Photo URLs always point at the guarded delivery endpoints -- filesystem paths
never leave the server.
"""

from __future__ import annotations

from app.config import settings
from app.models import Event, Photo
from app.schemas.event import EventOut, EventStats
from app.schemas.photo import PhotoOut


def photo_out(photo: Photo) -> PhotoOut:
    return PhotoOut(
        id=photo.id,
        filename=photo.filename,
        status=photo.status,
        file_size=photo.file_size,
        width=photo.width,
        height=photo.height,
        face_count=photo.face_count,
        error=photo.error,
        created_at=photo.created_at,
        thumbnail_url=f"/api/public/photos/{photo.id}/thumbnail",
        original_url=f"/api/public/photos/{photo.id}/original",
    )


def event_out(event: Event, stats: dict | None = None) -> EventOut:
    return EventOut(
        id=event.id,
        name=event.name,
        event_code=event.event_code,
        event_date=event.event_date,
        location=event.location,
        description=event.description,
        status=event.status,
        public_access=event.public_access,
        retention_days=event.retention_days,
        created_at=event.created_at,
        updated_at=event.updated_at,
        public_url=settings.event_url(event.event_code),
        stats=EventStats(**stats) if stats else None,
    )
