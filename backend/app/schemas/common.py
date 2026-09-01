"""Shared response envelopes."""

from __future__ import annotations

from pydantic import BaseModel


class Message(BaseModel):
    message: str


class ErrorDetail(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status: str
    database: bool
    face_engine: dict
    pending_tasks: int
    version: str
