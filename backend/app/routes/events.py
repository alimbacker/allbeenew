"""Photographer-side event management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import current_user, owned_event
from app.models import Event, User
from app.schemas.common import ErrorDetail, Message
from app.schemas.event import (
    DashboardOut,
    DashboardStats,
    EventCreate,
    EventOut,
    EventUpdate,
)
from app.routes.serializers import event_out
from app.services import events as event_service
from app.services.qr import event_qr_png

router = APIRouter(prefix="/api/events", tags=["Events"])

UNAUTHORISED = {401: {"model": ErrorDetail, "description": "Missing or invalid token"}}
NOT_FOUND = {404: {"model": ErrorDetail, "description": "Event not found or not yours"}}


@router.post(
    "",
    response_model=EventOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create an event",
    responses={**UNAUTHORISED},
)
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> EventOut:
    """Create an event and allocate its public code and storage folders.

    The event code (`EVT-8F42K9`) is generated server-side from an alphabet
    without look-alike characters, so guests can read it off a sign.
    """
    event = event_service.create_event(
        db,
        user,
        name=payload.name,
        event_date=payload.event_date,
        location=payload.location,
        description=payload.description,
    )
    return event_out(event, event_service.event_stats(db, event))


@router.get(
    "",
    response_model=list[EventOut],
    summary="List your events",
    responses={**UNAUTHORISED},
)
def list_events(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[EventOut]:
    """Newest first. Only ever returns events owned by the caller."""
    rows = (
        db.execute(
            select(Event)
            .where(Event.user_id == user.id)
            .order_by(desc(Event.created_at))
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return [event_out(e, event_service.event_stats(db, e)) for e in rows]


@router.get(
    "/dashboard",
    response_model=DashboardOut,
    summary="Dashboard totals and recent events",
    responses={**UNAUTHORISED},
)
def dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> DashboardOut:
    """Aggregate counters across every event this photographer owns."""
    recent = (
        db.execute(
            select(Event)
            .where(Event.user_id == user.id)
            .order_by(desc(Event.created_at))
            .limit(6)
        )
        .scalars()
        .all()
    )
    return DashboardOut(
        stats=DashboardStats(**event_service.dashboard_stats(db, user)),
        recent_events=[event_out(e, event_service.event_stats(db, e)) for e in recent],
    )


@router.get(
    "/{event_id}",
    response_model=EventOut,
    summary="Event detail with live counters",
    responses={**UNAUTHORISED, **NOT_FOUND},
)
def get_event(
    event: Event = Depends(owned_event), db: Session = Depends(get_db)
) -> EventOut:
    """Full event record plus photo, guest and match counts."""
    return event_out(event, event_service.event_stats(db, event))


@router.put(
    "/{event_id}",
    response_model=EventOut,
    summary="Update an event",
    responses={**UNAUTHORISED, **NOT_FOUND},
)
def update_event(
    payload: EventUpdate,
    event: Event = Depends(owned_event),
    db: Session = Depends(get_db),
) -> EventOut:
    """Patch any subset of fields, including status and public access."""
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(event, field, value)
    db.commit()
    db.refresh(event)
    return event_out(event, event_service.event_stats(db, event))


@router.delete(
    "/{event_id}",
    response_model=Message,
    summary="Delete an event and all its photos",
    responses={**UNAUTHORISED, **NOT_FOUND},
)
def delete_event(
    event: Event = Depends(owned_event), db: Session = Depends(get_db)
) -> Message:
    """Permanently remove the event, its database rows and its stored files."""
    name = event.name
    event_service.delete_event(db, event)
    return Message(message=f"Deleted {name!r} and all of its photos")


@router.get(
    "/{event_id}/qr",
    summary="Event QR code as PNG",
    response_class=Response,
    responses={
        200: {"content": {"image/png": {}}, "description": "QR code image"},
        **UNAUTHORISED,
        **NOT_FOUND,
    },
)
def event_qr(
    event: Event = Depends(owned_event),
    download: bool = Query(False, description="Send as a file attachment"),
    size: int = Query(12, ge=4, le=40, description="Pixels per QR module"),
) -> Response:
    """Render the guest URL for this event as a scannable PNG."""
    png = event_qr_png(event.event_code, box_size=size)
    headers = {"Cache-Control": "public, max-age=3600"}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{event.event_code}-qr.png"'
    return Response(content=png, media_type="image/png", headers=headers)
