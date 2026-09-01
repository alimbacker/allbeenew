"""Join row between a guest search and a photo, carrying the similarity score."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.guest_search import GuestSearch
    from app.models.photo import Photo


class PhotoMatch(Base, TimestampMixin):
    __tablename__ = "photo_matches"
    __table_args__ = (
        UniqueConstraint("guest_search_id", "photo_id", name="uq_match_search_photo"),
        Index("ix_matches_search_score", "guest_search_id", "similarity_score"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    guest_search_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("guest_searches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    photo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("photos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)

    search: Mapped["GuestSearch"] = relationship(back_populates="matches")
    photo: Mapped["Photo"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PhotoMatch {self.similarity_score:.3f}>"
