"""Photo ingestion and the background face-processing pipeline.

Upload path (synchronous, fast):
    validate -> hash -> reject duplicates -> save original -> thumbnail ->
    DB row (PROCESSING) -> hand off to the worker -> return

Worker path (background):
    decode -> detect faces -> embed -> store faces -> READY -> notify gallery

The request never waits on face detection, so a photographer uploading 500
photos is not blocked behind the model.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import session_scope
from app.face.base import FaceError
from app.face.engine import get_engine
from app.models import Event, Face, Photo, PhotoStatus
from app.services import images
from app.services.live import live_bus
from app.services.storage import storage
from app.services.tasks import task_queue
from app.utils.files import sanitize_filename, sha256_bytes, unique_stored_name

logger = logging.getLogger(__name__)

# Faces are detected on a downscaled copy for speed; boxes are scaled back so
# stored coordinates always refer to the original image.
FACE_DETECT_MAX_EDGE = 1920


class DuplicatePhotoError(Exception):
    def __init__(self, existing: Photo) -> None:
        self.existing = existing
        super().__init__("This photo has already been uploaded to this event")


@dataclass(slots=True)
class UploadResult:
    photo: Photo
    duplicate: bool = False


def ingest_photo(db: Session, event: Event, filename: str, data: bytes) -> UploadResult:
    """Validate and persist one uploaded photo, then queue it for face work."""
    if not data:
        raise images.InvalidImageError("File is empty")
    if len(data) > settings.max_upload_bytes:
        raise images.InvalidImageError(
            f"File is larger than the {settings.max_upload_size_mb} MB limit"
        )

    ext, width, height = images.inspect(data)
    file_hash = sha256_bytes(data)

    existing = db.execute(
        select(Photo).where(Photo.event_id == event.id, Photo.file_hash == file_hash)
    ).scalar_one_or_none()
    if existing is not None:
        raise DuplicatePhotoError(existing)

    display_name = sanitize_filename(filename, fallback=f"photo.{ext}")
    stored_name = unique_stored_name(display_name)
    thumb_name = f"{stored_name.rsplit('.', 1)[0]}.webp"

    storage.ensure_event_dirs(event.event_code)
    original_rel = storage.relative_path(event.event_code, "originals", stored_name)
    thumb_rel = storage.relative_path(event.event_code, "thumbnails", thumb_name)

    storage.write_bytes(original_rel, data)
    try:
        storage.write_bytes(thumb_rel, images.make_thumbnail(data))
    except Exception:  # noqa: BLE001 - a bad thumbnail must not lose the original
        logger.exception("Thumbnail generation failed for %s", display_name)
        thumb_rel = None

    photo = Photo(
        event_id=event.id,
        filename=display_name,
        original_path=original_rel,
        thumbnail_path=thumb_rel,
        status=PhotoStatus.PROCESSING,
        file_size=len(data),
        file_hash=file_hash,
        width=width,
        height=height,
    )
    db.add(photo)
    try:
        db.commit()
    except IntegrityError:
        # Two uploads of the same file raced. Roll back and treat as duplicate.
        db.rollback()
        storage.delete(original_rel)
        if thumb_rel:
            storage.delete(thumb_rel)
        dupe = db.execute(
            select(Photo).where(Photo.event_id == event.id, Photo.file_hash == file_hash)
        ).scalar_one_or_none()
        if dupe is not None:
            raise DuplicatePhotoError(dupe) from None
        raise
    db.refresh(photo)

    _notify(event.event_code, "photo.uploaded", photo)
    task_queue.submit(process_photo_faces, str(photo.id))
    return UploadResult(photo=photo)


def process_photo_faces(photo_id: str) -> int:
    """Detect and store every face in one photo. Runs on a worker thread."""
    db = session_scope()
    try:
        photo = db.get(Photo, _as_uuid(photo_id))
        if photo is None:
            logger.warning("Photo %s vanished before processing", photo_id)
            return 0

        event = db.get(Event, photo.event_id)
        event_code = event.event_code if event else ""

        try:
            data = storage.read_bytes(photo.original_path)
            image = images.decode_bgr(data, max_edge=FACE_DETECT_MAX_EDGE)
            detected = get_engine().detect(image)

            det_h, det_w = image.shape[:2]
            original_size = (photo.width or det_w, photo.height or det_h)

            db.query(Face).filter(Face.photo_id == photo.id).delete()
            for face in detected:
                db.add(
                    Face(
                        photo_id=photo.id,
                        event_id=photo.event_id,
                        embedding=[float(v) for v in face.embedding],
                        bounding_box=images.scale_box(
                            face.box.as_dict(), (det_w, det_h), original_size
                        ),
                        detection_score=face.score,
                    )
                )

            photo.face_count = len(detected)
            photo.status = PhotoStatus.READY
            photo.error = None
            db.commit()
            db.refresh(photo)
            logger.info("Processed %s: %d face(s)", photo.filename, len(detected))
            _notify(event_code, "photo.ready", photo)
            return len(detected)

        except FaceError as exc:
            db.rollback()
            _fail(db, photo, f"Face processing unavailable: {exc}")
            _notify(event_code, "photo.failed", photo)
            return 0
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.exception("Face processing failed for %s", photo_id)
            _fail(db, photo, str(exc)[:500])
            _notify(event_code, "photo.failed", photo)
            return 0
    finally:
        db.close()


def reprocess_event(event_id: str) -> int:
    """Queue every non-ready photo in an event. Used after fixing model setup."""
    db = session_scope()
    try:
        rows = db.execute(
            select(Photo.id).where(
                Photo.event_id == _as_uuid(event_id),
                Photo.status.in_([PhotoStatus.FAILED, PhotoStatus.PROCESSING]),
            )
        ).scalars().all()
        for pid in rows:
            task_queue.submit(process_photo_faces, str(pid))
        return len(rows)
    finally:
        db.close()


def delete_photo(db: Session, photo: Photo) -> None:
    """Remove the DB row and both files. Faces cascade."""
    storage.delete(photo.original_path)
    if photo.thumbnail_path:
        storage.delete(photo.thumbnail_path)
    event = db.get(Event, photo.event_id)
    code = event.event_code if event else ""
    photo_id = str(photo.id)
    db.delete(photo)
    db.commit()
    live_bus.publish(code, "photo.deleted", {"id": photo_id})


# -- internals ---------------------------------------------------------------
def _fail(db: Session, photo: Photo, message: str) -> None:
    photo.status = PhotoStatus.FAILED
    photo.error = message
    db.commit()


def _notify(event_code: str, event_name: str, photo: Photo) -> None:
    if not event_code:
        return
    live_bus.publish(
        event_code,
        event_name,
        {
            "id": str(photo.id),
            "filename": photo.filename,
            "status": photo.status.value,
            "face_count": photo.face_count,
            "width": photo.width,
            "height": photo.height,
            "created_at": photo.created_at.isoformat() if photo.created_at else None,
        },
    )


def _as_uuid(value):
    import uuid

    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
