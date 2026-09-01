"""Guest-facing response models."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.photo import PhotoOut


class PublicEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    event_code: str
    event_date: date | None
    location: str | None
    description: str | None
    photo_count: int
    is_live: bool


class MatchOut(BaseModel):
    photo: PhotoOut
    similarity: float = Field(..., ge=-1.0, le=1.0)


class SearchResponse(BaseModel):
    search_id: uuid.UUID
    event_code: str
    match_count: int
    threshold: float
    matches: list[MatchOut]
    created_at: datetime


class SearchErrorResponse(BaseModel):
    code: str = Field(..., description="NO_FACE | MULTIPLE_FACES | INVALID_IMAGE | ENGINE_UNAVAILABLE")
    message: str
