"""Event request/response models."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.event import EventStatus


class EventCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200, examples=["Mohamed Wedding"])
    event_date: date | None = Field(None, examples=["2026-09-01"])
    location: str | None = Field(None, max_length=200, examples=["Nagore"])
    description: str | None = Field(None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Event name cannot be blank")
        return v


class EventUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=200)
    event_date: date | None = None
    location: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=2000)
    status: EventStatus | None = None
    public_access: bool | None = None
    retention_days: int | None = Field(None, ge=0, le=3650)


class EventStats(BaseModel):
    photos: int = 0
    processed: int = 0
    processing: int = 0
    failed: int = 0
    faces: int = 0
    guests: int = 0
    matches: int = 0


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    event_code: str
    event_date: date | None
    location: str | None
    description: str | None
    status: EventStatus
    public_access: bool
    retention_days: int | None
    created_at: datetime
    updated_at: datetime
    public_url: str
    stats: EventStats | None = None


class DashboardStats(BaseModel):
    total_events: int
    active_events: int
    total_photos: int
    photos_delivered: int
    total_guests: int


class DashboardOut(BaseModel):
    stats: DashboardStats
    recent_events: list[EventOut]
