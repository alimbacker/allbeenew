"""Declarative base, shared mixins and the embedding column type."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, JSON, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import settings


class Base(DeclarativeBase):
    pass


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )


def embedding_column_type(dim: int | None = None):
    """Return ``vector(dim)`` on PostgreSQL and a JSON array everywhere else.

    Keeping this in one place means the rest of the codebase never has to care
    which database is behind it. pgvector gives us indexed ANN search; the JSON
    variant lets the test suite and a laptop-only setup run unchanged.
    """
    dim = dim or settings.embedding_dim
    try:
        from pgvector.sqlalchemy import Vector

        return JSON().with_variant(Vector(dim), "postgresql")
    except ImportError:  # pragma: no cover - pgvector is a hard dep in prod
        return JSON()
