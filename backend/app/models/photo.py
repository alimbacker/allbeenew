"""A photo row. Bytes live on disk; only paths and metadata live here."""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.face import Face


class PhotoStatus(str, enum.Enum):
    UPLOADING = "UPLOADING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class Photo(Base, TimestampMixin):
    __tablename__ = "photos"
    __table_args__ = (
        # Duplicate protection is per event, not global: two photographers may
        # legitimately upload the same file to different events.
        UniqueConstraint("event_id", "file_hash", name="uq_photos_event_hash"),
        Index("ix_photos_event_created", "event_id", "created_at"),
        Index("ix_photos_event_status", "event_id", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_path: Mapped[str] = mapped_column(String(512), nullable=False)
    thumbnail_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    status: Mapped[PhotoStatus] = mapped_column(
        Enum(PhotoStatus, name="photo_status", native_enum=False, length=16),
        nullable=False,
        default=PhotoStatus.UPLOADING,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    face_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    event: Mapped["Event"] = relationship(back_populates="photos")
    faces: Mapped[list["Face"]] = relationship(
        back_populates="photo", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Photo {self.filename} {self.status}>"
