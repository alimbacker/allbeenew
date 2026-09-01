"""Guest-facing endpoints. No account, no token -- the event code is the key."""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import public_event
from app.models import Event, GuestSearch, Photo, PhotoStatus
from app.routes.serializers import photo_out
from app.schemas.common import ErrorDetail
from app.schemas.photo import PhotoPage
from app.schemas.public import MatchOut, PublicEventOut, SearchErrorResponse, SearchResponse
from app.services import search as search_service
from app.services.live import live_bus, sse_format
from app.services.rate_limit import enforce, search_limiter
from app.services.storage import storage

router = APIRouter(prefix="/api/public", tags=["Guest"])

EVENT_ERRORS = {
    404: {"model": ErrorDetail, "description": "No event with that code"},
    403: {"model": ErrorDetail, "description": "The gallery is closed"},
}

# Guest galleries change constantly; the browser should revalidate. Image bytes
# are immutable once written, so those get a long cache instead.
NO_STORE = {"Cache-Control": "no-store"}
IMAGE_CACHE = {"Cache-Control": "public, max-age=604800, immutable"}


@router.get(
    "/events/{event_code}",
    response_model=PublicEventOut,
    summary="Event details for guests",
    responses={**EVENT_ERRORS},
)
def get_event(event: Event = Depends(public_event), db: Session = Depends(get_db)) -> PublicEventOut:
    """Everything the guest landing page needs. No photographer data is exposed."""
    count = db.execute(
        select(func.count(Photo.id)).where(
            Photo.event_id == event.id, Photo.status == PhotoStatus.READY
        )
    ).scalar_one()
    return PublicEventOut(
        name=event.name,
        event_code=event.event_code,
        event_date=event.event_date,
        location=event.location,
        description=event.description,
        photo_count=count,
        is_live=event.is_publicly_visible,
    )


@router.get(
    "/events/{event_code}/photos",
    response_model=PhotoPage,
    summary="Live gallery, newest first",
    responses={**EVENT_ERRORS},
)
def list_photos(
    event: Event = Depends(public_event),
    db: Session = Depends(get_db),
    limit: int = Query(48, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> PhotoPage:
    """Only READY photos appear, so guests never see a half-processed frame."""
    conditions = [Photo.event_id == event.id, Photo.status == PhotoStatus.READY]
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
    "/events/{event_code}/stream",
    summary="Server-Sent Events feed of new photos",
    responses={200: {"content": {"text/event-stream": {}}}, **EVENT_ERRORS},
)
async def stream(request: Request, event: Event = Depends(public_event)) -> StreamingResponse:
    """Push new photos to the gallery as they finish processing.

    Clients that cannot hold an SSE connection open (some corporate proxies,
    older mobile browsers) fall back to polling `/photos`; both paths return the
    same shape, so the UI code is identical.
    """
    channel = event.event_code

    async def generator():
        with live_bus.subscribe(channel) as queue:
            yield sse_format("connected", {"event_code": channel})
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=20.0)
                except asyncio.TimeoutError:
                    # Comment frame: keeps proxies and load balancers from
                    # closing an idle connection.
                    yield ": keep-alive\n\n"
                    continue
                yield sse_format(payload["event"], payload["data"])

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # tells Nginx not to buffer the stream
        },
    )


@router.post(
    "/events/{event_code}/search",
    response_model=SearchResponse,
    summary="Find my photos from a selfie",
    responses={
        **EVENT_ERRORS,
        422: {"model": SearchErrorResponse, "description": "Selfie unusable"},
        429: {"model": ErrorDetail, "description": "Too many searches"},
        503: {"model": SearchErrorResponse, "description": "Face engine unavailable"},
    },
)
async def search(
    request: Request,
    selfie: UploadFile = File(..., description="A single clear photo of the guest's face"),
    event: Event = Depends(public_event),
    db: Session = Depends(get_db),
) -> SearchResponse:
    """Match a guest's selfie against this event's photos.

    The search is scoped to `faces.event_id = this event`, so photos from any
    other event are unreachable no matter what is submitted.

    Rejects a selfie with no detectable face, or with more than one, and returns
    a machine-readable `code` the UI turns into specific guidance.
    """
    enforce(search_limiter, request, "search")

    data = await selfie.read()
    await selfie.close()

    try:
        outcome = search_service.search_event(db, event, data)
    except search_service.SelfieError as exc:
        code = status.HTTP_422_UNPROCESSABLE_ENTITY
        if exc.code == search_service.ENGINE_UNAVAILABLE:
            code = status.HTTP_503_SERVICE_UNAVAILABLE
        raise HTTPException(
            status_code=code, detail={"code": exc.code, "message": str(exc)}
        ) from exc

    return SearchResponse(
        search_id=outcome.search.id,
        event_code=event.event_code,
        match_count=len(outcome.matches),
        threshold=outcome.threshold,
        matches=[
            MatchOut(photo=photo_out(m.photo), similarity=round(m.score, 4))
            for m in outcome.matches
        ],
        created_at=outcome.search.created_at,
    )


@router.get(
    "/searches/{search_id}",
    response_model=SearchResponse,
    summary="Re-open a previous search",
    responses={404: {"model": ErrorDetail, "description": "Search not found"}},
)
def get_search(search_id: uuid.UUID, db: Session = Depends(get_db)) -> SearchResponse:
    """Fetch results again without re-uploading the selfie.

    The ID is a random UUID, so it is not guessable from the event code.
    """
    record = db.get(GuestSearch, search_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Search not found")
    event = db.get(Event, record.event_id)
    if event is None or not event.is_publicly_visible:
        raise HTTPException(status_code=404, detail="Search not found")

    matches = search_service.matches_for_search(db, record)
    return SearchResponse(
        search_id=record.id,
        event_code=event.event_code,
        match_count=len(matches),
        threshold=settings.face_match_threshold,
        matches=[
            MatchOut(photo=photo_out(m.photo), similarity=round(m.score, 4)) for m in matches
        ],
        created_at=record.created_at,
    )


# -- guarded file delivery ---------------------------------------------------
def _serve(photo_id: uuid.UUID, db: Session, kind: str, download: bool) -> FileResponse:
    """Shared delivery path for thumbnails and originals.

    Three checks happen before any byte is read: the photo exists, its event is
    publicly visible, and the stored path resolves inside the storage root.
    """
    photo = db.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    event = db.get(Event, photo.event_id)
    if event is None or not event.is_publicly_visible:
        raise HTTPException(status_code=404, detail="Photo not found")

    relative = photo.thumbnail_path if kind == "thumbnail" else photo.original_path
    if not relative:
        raise HTTPException(status_code=404, detail="Photo not found")

    try:
        path = storage.absolute(relative)
    except ValueError:
        raise HTTPException(status_code=404, detail="Photo not found") from None
    if not path.exists():
        raise HTTPException(status_code=404, detail="Photo not found")

    headers = dict(IMAGE_CACHE)
    kwargs: dict = {}
    if download:
        kwargs["filename"] = photo.filename
        kwargs["media_type"] = "application/octet-stream"
    elif kind == "thumbnail":
        kwargs["media_type"] = "image/webp"

    return FileResponse(path, headers=headers, **kwargs)


@router.get(
    "/photos/{photo_id}/thumbnail",
    summary="Gallery-sized thumbnail",
    response_class=FileResponse,
    responses={200: {"content": {"image/webp": {}}}, 404: {"model": ErrorDetail}},
)
def photo_thumbnail(photo_id: uuid.UUID, db: Session = Depends(get_db)) -> FileResponse:
    """The small WEBP used everywhere a grid of photos is shown."""
    return _serve(photo_id, db, "thumbnail", download=False)


@router.get(
    "/photos/{photo_id}/original",
    summary="Full-resolution photo",
    response_class=FileResponse,
    responses={200: {"content": {"image/*": {}}}, 404: {"model": ErrorDetail}},
)
def photo_original(
    photo_id: uuid.UUID,
    db: Session = Depends(get_db),
    download: bool = Query(False, description="Send as a file attachment"),
) -> FileResponse:
    """Used by the fullscreen viewer and by the guest download button."""
    return _serve(photo_id, db, "original", download=download)
