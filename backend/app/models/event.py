"""An event is the unit of isolation: photos, faces and searches all hang off it."""

from __future__ import annotations

import enum
import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.guest_search import GuestSearch
    from app.models.photo import Photo
    from app.models.user import User


class EventStatus(str, enum.Enum):
    LIVE = "LIVE"
    ARCHIVED = "ARCHIVED"


class Event(Base, TimestampMixin):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    event_code: Mapped[str] = mapped_column(String(24), nullable=False, unique=True, index=True)
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus, name="event_status", native_enum=False, length=16),
        nullable=False,
        default=EventStatus.LIVE,
    )
    # Lets a photographer archive an event but keep the guest gallery reachable,
    # or close public access while still working on it.
    public_access: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Reserved for the retention policy described in docs/PRIVACY.md.
    # NULL means "inherit the server default"; the server default of 0 means never.
    retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    owner: Mapped["User"] = relationship(back_populates="events")
    photos: Mapped[list["Photo"]] = relationship(
        back_populates="event", cascade="all, delete-orphan", passive_deletes=True
    )
    searches: Mapped[list["GuestSearch"]] = relationship(
        back_populates="event", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def is_publicly_visible(self) -> bool:
        return self.public_access and self.status == EventStatus.LIVE

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Event {self.event_code} {self.name!r}>"
