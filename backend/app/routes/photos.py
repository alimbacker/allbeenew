"""Photo upload, listing and deletion (photographer side)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import owned_event, owned_photo
from app.models import Event, Photo, PhotoStatus
from app.routes.serializers import photo_out
from app.schemas.common import ErrorDetail, Message
from app.schemas.photo import PhotoOut, PhotoPage, UploadItemResult, UploadResponse
from app.services import photos as photo_service
from app.services.images import InvalidImageError
from app.services.rate_limit import enforce, upload_limiter
from app.services.storage import storage

router = APIRouter(tags=["Photos"])

UNAUTHORISED = {401: {"model": ErrorDetail, "description": "Missing or invalid token"}}
NOT_FOUND = {404: {"model": ErrorDetail, "description": "Not found or not yours"}}


@router.post(
    "/api/events/{event_id}/photos",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload one or more photos",
    responses={
        **UNAUTHORISED,
        **NOT_FOUND,
        413: {"model": ErrorDetail, "description": "File exceeds MAX_UPLOAD_SIZE_MB"},
        429: {"model": ErrorDetail, "description": "Upload rate limit exceeded"},
    },
)
async def upload_photos(
    request: Request,
    files: list[UploadFile] = File(..., description="JPG, JPEG, PNG or WEBP images"),
    event: Event = Depends(owned_event),
    db: Session = Depends(get_db),
) -> UploadResponse:
    """Store photos and queue face processing.

    Each file is reported independently, so one bad frame in a batch of 200 does
    not fail the rest. Duplicates are detected by SHA-256 and reported as
    `duplicate` rather than as an error.

    The response returns as soon as files are written and thumbnails generated;
    face detection continues in the background and the photo moves from
    `PROCESSING` to `READY`.
    """
    enforce(upload_limiter, request, "upload")

    results: list[UploadItemResult] = []
    uploaded = duplicates = rejected = 0

    for upload in files:
        name = upload.filename or "photo.jpg"
        try:
            data = await upload.read()
            result = photo_service.ingest_photo(db, event, name, data)
            uploaded += 1
            results.append(
                UploadItemResult(filename=name, status="uploaded", photo=photo_out(result.photo))
            )
        except photo_service.DuplicatePhotoError as exc:
            duplicates += 1
            results.append(
                UploadItemResult(
                    filename=name,
                    status="duplicate",
                    photo=photo_out(exc.existing),
                    error="Already uploaded to this event",
                )
            )
        except InvalidImageError as exc:
            rejected += 1
            results.append(UploadItemResult(filename=name, status="rejected", error=str(exc)))
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            rejected += 1
            results.append(UploadItemResult(filename=name, status="rejected", error=str(exc)))
        finally:
            await upload.close()

    return UploadResponse(
        uploaded=uploaded, duplicates=duplicates, rejected=rejected, results=results
    )


@router.get(
    "/api/events/{event_id}/photos",
    response_model=PhotoPage,
    summary="List an event's photos",
    responses={**UNAUTHORISED, **NOT_FOUND},
)
def list_photos(
    event: Event = Depends(owned_event),
    db: Session = Depends(get_db),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status_filter: PhotoStatus | None = Query(None, alias="status"),
) -> PhotoPage:
    """Newest first, paginated. Never loads a whole event into memory."""
    conditions = [Photo.event_id == event.id]
    if status_filter is not None:
        conditions.append(Photo.status == status_filter)

    total = db.execute(select(func.count(Photo.id)).where(*conditions)).scalar_one()
    rows = (
        db.execute(
            select(Photo)
            .where(*conditions)
            .order_by(desc(Photo.created_at), desc(Photo.id))
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return PhotoPage(
        items=[photo_out(p) for p in rows],
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(rows) < total,
    )


@router.get(
    "/api/photos/{photo_id}",
    response_model=PhotoOut,
    summary="Photo detail",
    responses={**UNAUTHORISED, **NOT_FOUND},
)
def get_photo(photo: Photo = Depends(owned_photo)) -> PhotoOut:
    """Metadata and processing status for one photo."""
    return photo_out(photo)


@router.delete(
    "/api/photos/{photo_id}",
    response_model=Message,
    summary="Delete a photo",
    responses={**UNAUTHORISED, **NOT_FOUND},
)
def delete_photo(
    photo: Photo = Depends(owned_photo), db: Session = Depends(get_db)
) -> Message:
    """Remove the row, its faces, the original and the thumbnail."""
    name = photo.filename
    photo_service.delete_photo(db, photo)
    return Message(message=f"Deleted {name}")


@router.post(
    "/api/events/{event_id}/photos/reprocess",
    response_model=Message,
    summary="Re-run face detection on failed photos",
    responses={**UNAUTHORISED, **NOT_FOUND},
)
def reprocess(event: Event = Depends(owned_event)) -> Message:
    """Requeue every photo stuck in PROCESSING or FAILED.

    Useful after fixing a model download or changing FACE_ENGINE.
    """
    count = photo_service.reprocess_event(str(event.id))
    return Message(message=f"Queued {count} photo(s) for reprocessing")


@router.get(
    "/api/photos/{photo_id}/original",
    summary="Download the full-resolution original (photographer)",
    response_class=FileResponse,
    responses={200: {"content": {"image/*": {}}}, **UNAUTHORISED, **NOT_FOUND},
)
def download_original(
    photo: Photo = Depends(owned_photo),
    download: bool = Query(True, description="Send as an attachment"),
) -> FileResponse:
    """Serve the original file to its owner through a guarded endpoint.

    The storage directory is never exposed by the web server; the path is
    resolved and bounds-checked here before the file is read.
    """
    try:
        path = storage.absolute(photo.original_path)
    except ValueError:
        raise HTTPException(status_code=404, detail="File not found") from None
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path,
        media_type="application/octet-stream" if download else None,
        filename=photo.filename if download else None,
        headers={"Cache-Control": f"private, max-age={60 * 60}"},
    )
