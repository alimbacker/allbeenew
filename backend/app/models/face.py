"""One detected face inside one photo."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Float, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, embedding_column_type, uuid_pk

if TYPE_CHECKING:
    from app.models.photo import Photo


class Face(Base, TimestampMixin):
    __tablename__ = "faces"
    __table_args__ = (Index("ix_faces_event", "event_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    photo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("photos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Denormalised from photos on purpose: the guest search filters by event on
    # every query, and carrying event_id here avoids a join inside the ANN scan.
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )

    embedding: Mapped[list[float]] = mapped_column(embedding_column_type(), nullable=False)
    bounding_box: Mapped[dict] = mapped_column(JSON, nullable=False)
    detection_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    photo: Mapped["Photo"] = relationship(back_populates="faces")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Face photo={self.photo_id}>"
