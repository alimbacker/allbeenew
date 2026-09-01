"""Initial schema: users, events, photos, faces, guest searches, matches.

Revision ID: 0001
Revises:
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.config import settings

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

EMBEDDING_DIM = settings.embedding_dim


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _embedding_type():
    if _is_postgres():
        from pgvector.sqlalchemy import Vector

        return Vector(EMBEDDING_DIM)
    return sa.JSON()


def upgrade() -> None:
    if _is_postgres():
        # Needs a superuser the first time. docker-compose.yml runs this for you.
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("event_code", sa.String(24), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="LIVE"),
        sa.Column("public_access", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("retention_days", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_events_event_code", "events", ["event_code"], unique=True)
    op.create_index("ix_events_user_id", "events", ["user_id"])
    op.create_index("ix_events_user_created", "events", ["user_id", "created_at"])

    op.create_table(
        "photos",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("event_id", sa.Uuid(as_uuid=True), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("original_path", sa.String(512), nullable=False),
        sa.Column("thumbnail_path", sa.String(512), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="UPLOADING"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("face_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("event_id", "file_hash", name="uq_photos_event_hash"),
    )
    op.create_index("ix_photos_event_id", "photos", ["event_id"])
    op.create_index("ix_photos_file_hash", "photos", ["file_hash"])
    op.create_index("ix_photos_event_created", "photos", ["event_id", "created_at"])
    op.create_index("ix_photos_event_status", "photos", ["event_id", "status"])

    op.create_table(
        "faces",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("photo_id", sa.Uuid(as_uuid=True), sa.ForeignKey("photos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", sa.Uuid(as_uuid=True), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("embedding", _embedding_type(), nullable=False),
        sa.Column("bounding_box", sa.JSON(), nullable=False),
        sa.Column("detection_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_faces_photo_id", "faces", ["photo_id"])
    op.create_index("ix_faces_event", "faces", ["event_id"])

    if _is_postgres():
        # HNSW gives good recall with predictable latency and, unlike IVFFlat,
        # needs no training pass -- which matters because faces arrive
        # continuously during an event rather than in one bulk load.
        op.execute(
            "CREATE INDEX ix_faces_embedding_hnsw ON faces "
            "USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        )

    op.create_table(
        "guest_searches",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("event_id", sa.Uuid(as_uuid=True), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("selfie_path", sa.String(512), nullable=True),
        sa.Column("match_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_guest_searches_event_id", "guest_searches", ["event_id"])

    op.create_table(
        "photo_matches",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("guest_search_id", sa.Uuid(as_uuid=True), sa.ForeignKey("guest_searches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("photo_id", sa.Uuid(as_uuid=True), sa.ForeignKey("photos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("guest_search_id", "photo_id", name="uq_match_search_photo"),
    )
    op.create_index("ix_photo_matches_guest_search_id", "photo_matches", ["guest_search_id"])
    op.create_index("ix_photo_matches_photo_id", "photo_matches", ["photo_id"])
    op.create_index("ix_matches_search_score", "photo_matches", ["guest_search_id", "similarity_score"])


def downgrade() -> None:
    op.drop_table("photo_matches")
    op.drop_table("guest_searches")
    if _is_postgres():
        op.execute("DROP INDEX IF EXISTS ix_faces_embedding_hnsw")
    op.drop_table("faces")
    op.drop_table("photos")
    op.drop_table("events")
    op.drop_table("users")
