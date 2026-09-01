"""Photo request/response models."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.photo import PhotoStatus


class PhotoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    status: PhotoStatus
    file_size: int
    width: int | None
    height: int | None
    face_count: int
    error: str | None
    created_at: datetime
    thumbnail_url: str
    original_url: str


class PhotoPage(BaseModel):
    items: list[PhotoOut]
    total: int
    limit: int
    offset: int
    has_more: bool


class UploadItemResult(BaseModel):
    filename: str
    status: str = Field(..., description="uploaded | duplicate | rejected")
    photo: PhotoOut | None = None
    error: str | None = None


class UploadResponse(BaseModel):
    uploaded: int
    duplicates: int
    rejected: int
    results: list[UploadItemResult]
