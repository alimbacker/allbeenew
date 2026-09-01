"""Shared FastAPI dependencies.

Authorisation lives here rather than being repeated in each route, so a new
endpoint gets ownership checks by declaring the dependency instead of by
remembering to write an `if`.
"""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, Path, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Event, Photo, User
from app.services.events import get_owned_event, get_public_event
from app.services.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False, description="JWT from /api/auth/login")

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the signed-in photographer, or 401."""
    if credentials is None or not credentials.credentials:
        raise CREDENTIALS_ERROR
    claims = decode_access_token(credentials.credentials)
    if not claims or claims.get("typ") != "access":
        raise CREDENTIALS_ERROR
    try:
        user_id = uuid.UUID(str(claims.get("sub")))
    except (TypeError, ValueError):
        raise CREDENTIALS_ERROR from None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise CREDENTIALS_ERROR
    return user


def owned_event(
    event_id: uuid.UUID = Path(..., description="Event UUID"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Event:
    """An event the signed-in photographer owns.

    Returns 404 (not 403) for someone else's event so the API does not confirm
    that an unknown event ID exists.
    """
    event = get_owned_event(db, event_id, user)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


def owned_photo(
    photo_id: uuid.UUID = Path(..., description="Photo UUID"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Photo:
    photo = db.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    event = db.get(Event, photo.event_id)
    if event is None or event.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    return photo


def public_event(
    event_code: str = Path(..., description="Public event code, e.g. EVT-8F42K9"),
    db: Session = Depends(get_db),
) -> Event:
    """An event reachable by guests via its code."""
    event = get_public_event(db, event_code)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    if not event.is_publicly_visible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This gallery is closed. Ask your photographer to reopen it.",
        )
    return event
