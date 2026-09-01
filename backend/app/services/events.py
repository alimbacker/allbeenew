"""Event creation, lookup and statistics."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Event, EventStatus, Face, GuestSearch, Photo, PhotoMatch, PhotoStatus, User
from app.services.storage import storage
from app.utils.codes import generate_event_code, normalise_event_code

MAX_CODE_ATTEMPTS = 8


def create_event(db: Session, owner: User, **fields) -> Event:
    """Create an event, retrying if the generated code happens to collide."""
    last_error: Exception | None = None
    for _ in range(MAX_CODE_ATTEMPTS):
        event = Event(user_id=owner.id, event_code=generate_event_code(), **fields)
        db.add(event)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            last_error = exc
            continue
        db.refresh(event)
        storage.ensure_event_dirs(event.event_code)
        return event
    raise RuntimeError("Could not allocate a unique event code") from last_error


def get_owned_event(db: Session, event_id: uuid.UUID, owner: User) -> Event | None:
    """Fetch an event only if this photographer owns it.

    Ownership is part of the query rather than a check afterwards, so there is
    no path where a missing check leaks another photographer's event.
    """
    return db.execute(
        select(Event).where(Event.id == event_id, Event.user_id == owner.id)
    ).scalar_one_or_none()


def get_public_event(db: Session, event_code: str) -> Event | None:
    """Fetch an event by its public code, regardless of visibility."""
    code = normalise_event_code(event_code)
    return db.execute(select(Event).where(Event.event_code == code)).scalar_one_or_none()


def event_stats(db: Session, event: Event) -> dict:
    counts = dict(
        db.execute(
            select(Photo.status, func.count(Photo.id))
            .where(Photo.event_id == event.id)
            .group_by(Photo.status)
        ).all()
    )
    total = sum(counts.values())
    ready = counts.get(PhotoStatus.READY, 0)

    guests = db.execute(
        select(func.count(GuestSearch.id)).where(GuestSearch.event_id == event.id)
    ).scalar_one()
    matches = db.execute(
        select(func.count(PhotoMatch.id))
        .join(GuestSearch, GuestSearch.id == PhotoMatch.guest_search_id)
        .where(GuestSearch.event_id == event.id)
    ).scalar_one()
    faces = db.execute(
        select(func.count(Face.id)).where(Face.event_id == event.id)
    ).scalar_one()

    return {
        "photos": total,
        "processed": ready,
        "processing": counts.get(PhotoStatus.PROCESSING, 0) + counts.get(PhotoStatus.UPLOADING, 0),
        "failed": counts.get(PhotoStatus.FAILED, 0),
        "faces": faces,
        "guests": guests,
        "matches": matches,
    }


def dashboard_stats(db: Session, owner: User) -> dict:
    event_ids = select(Event.id).where(Event.user_id == owner.id).scalar_subquery()

    total_events = db.execute(
        select(func.count(Event.id)).where(Event.user_id == owner.id)
    ).scalar_one()
    active_events = db.execute(
        select(func.count(Event.id)).where(
            Event.user_id == owner.id, Event.status == EventStatus.LIVE
        )
    ).scalar_one()
    total_photos = db.execute(
        select(func.count(Photo.id)).where(Photo.event_id.in_(event_ids))
    ).scalar_one()
    delivered = db.execute(
        select(func.count(PhotoMatch.id))
        .join(GuestSearch, GuestSearch.id == PhotoMatch.guest_search_id)
        .where(GuestSearch.event_id.in_(event_ids))
    ).scalar_one()
    guests = db.execute(
        select(func.count(GuestSearch.id)).where(GuestSearch.event_id.in_(event_ids))
    ).scalar_one()

    return {
        "total_events": total_events,
        "active_events": active_events,
        "total_photos": total_photos,
        "photos_delivered": delivered,
        "total_guests": guests,
    }


def delete_event(db: Session, event: Event) -> None:
    """Delete an event, its rows and its whole storage directory."""
    code = event.event_code
    db.delete(event)
    db.commit()
    storage.delete_event(code)
