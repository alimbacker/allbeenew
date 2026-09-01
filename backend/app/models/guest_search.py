"""A guest's selfie search. No account, no PII beyond the selfie itself."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.photo_match import PhotoMatch


class GuestSearch(Base, TimestampMixin):
    __tablename__ = "guest_searches"

    id: Mapped[uuid.UUID] = uuid_pk()
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    selfie_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    match_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    event: Mapped["Event"] = relationship(back_populates="searches")
    matches: Mapped[list["PhotoMatch"]] = relationship(
        back_populates="search", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<GuestSearch {self.id} matches={self.match_count}>"
