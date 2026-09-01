"""Guest face search.

A guest submits one selfie. We detect exactly one face, embed it, and compare
it against the faces of *this event only*. Two execution strategies share one
signature:

* PostgreSQL + pgvector -- an indexed ANN scan using the cosine operator. This
  is the production path and stays fast as an event grows past 5,000 photos.
* Anything else -- embeddings are loaded and compared with numpy. Correct and
  perfectly usable for development and tests, linear in the number of faces.

Cross-event leakage is structurally impossible here: every query is filtered by
``faces.event_id``, and the event is resolved from the guest's event code
before the search runs.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

import numpy as np
from sqlalchemy import bindparam, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.face.base import FaceError
from app.face.engine import get_engine
from app.models import Event, Face, GuestSearch, Photo, PhotoMatch, PhotoStatus
from app.services import images
from app.services.storage import storage
from app.utils.files import unique_stored_name

logger = logging.getLogger(__name__)


class SelfieError(Exception):
    """A selfie we cannot search with. ``code`` drives the guest-facing copy."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


NO_FACE = "NO_FACE"
MULTIPLE_FACES = "MULTIPLE_FACES"
INVALID_IMAGE = "INVALID_IMAGE"
ENGINE_UNAVAILABLE = "ENGINE_UNAVAILABLE"


@dataclass(slots=True)
class MatchedPhoto:
    photo: Photo
    score: float


@dataclass(slots=True)
class SearchOutcome:
    search: GuestSearch
    matches: list[MatchedPhoto]
    threshold: float


def embed_selfie(data: bytes) -> np.ndarray:
    """Validate a selfie and return its unit-length embedding.

    Raises SelfieError with a code the API turns into the exact guest message.
    """
    if not data:
        raise SelfieError(INVALID_IMAGE, "The selfie file is empty")
    if len(data) > settings.max_upload_bytes:
        raise SelfieError(
            INVALID_IMAGE, f"Selfie is larger than the {settings.max_upload_size_mb} MB limit"
        )
    try:
        images.inspect(data)
        image = images.decode_bgr(data, max_edge=1280)
    except images.InvalidImageError as exc:
        raise SelfieError(INVALID_IMAGE, str(exc)) from exc

    try:
        faces = get_engine().detect(image)
    except FaceError as exc:
        raise SelfieError(ENGINE_UNAVAILABLE, str(exc)) from exc

    if not faces:
        raise SelfieError(NO_FACE, "No face detected in the selfie")
    if len(faces) > 1:
        raise SelfieError(MULTIPLE_FACES, "More than one face detected in the selfie")
    return faces[0].embedding


def search_event(
    db: Session,
    event: Event,
    selfie_bytes: bytes,
    threshold: float | None = None,
    limit: int | None = None,
    store_selfie: bool = True,
) -> SearchOutcome:
    """Run one guest search and persist it with its matches."""
    threshold = settings.face_match_threshold if threshold is None else threshold
    limit = limit or settings.face_max_results

    embedding = embed_selfie(selfie_bytes)

    selfie_rel: str | None = None
    if store_selfie:
        storage.ensure_event_dirs(event.event_code)
        selfie_rel = storage.relative_path(
            event.event_code, "selfies", unique_stored_name("selfie.jpg")
        )
        storage.write_bytes(selfie_rel, selfie_bytes)

    scored = _rank_photos(db, event.id, embedding, threshold, limit)

    guest_search = GuestSearch(
        event_id=event.id, selfie_path=selfie_rel, match_count=len(scored)
    )
    db.add(guest_search)
    db.flush()

    for photo_id, score in scored:
        db.add(
            PhotoMatch(
                guest_search_id=guest_search.id, photo_id=photo_id, similarity_score=float(score)
            )
        )
    db.commit()
    db.refresh(guest_search)

    matches = _load_matches(db, [pid for pid, _ in scored], dict(scored))
    logger.info(
        "Guest search on %s: %d match(es) at threshold %.2f",
        event.event_code,
        len(matches),
        threshold,
    )
    return SearchOutcome(search=guest_search, matches=matches, threshold=threshold)


def matches_for_search(db: Session, search: GuestSearch) -> list[MatchedPhoto]:
    """Re-read a previous search's results, best first."""
    rows = db.execute(
        select(PhotoMatch, Photo)
        .join(Photo, Photo.id == PhotoMatch.photo_id)
        .where(PhotoMatch.guest_search_id == search.id)
        .order_by(PhotoMatch.similarity_score.desc())
    ).all()
    return [MatchedPhoto(photo=photo, score=match.similarity_score) for match, photo in rows]


# -- ranking strategies ------------------------------------------------------
def _rank_photos(
    db: Session,
    event_id: uuid.UUID,
    embedding: np.ndarray,
    threshold: float,
    limit: int,
) -> list[tuple[uuid.UUID, float]]:
    """Best score per photo, above threshold, ordered descending."""
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        try:
            return _rank_pgvector(db, event_id, embedding, threshold, limit)
        except Exception:  # noqa: BLE001 - e.g. pgvector extension absent
            logger.warning("pgvector search failed, falling back to numpy", exc_info=True)
    return _rank_numpy(db, event_id, embedding, threshold, limit)


def _rank_pgvector(
    db: Session, event_id: uuid.UUID, embedding: np.ndarray, threshold: float, limit: int
) -> list[tuple[uuid.UUID, float]]:
    """Indexed cosine search.

    ``<=>`` is pgvector's cosine *distance*; for unit vectors similarity is
    1 - distance. DISTINCT ON collapses the several faces a photo may contain
    down to that photo's single best score.
    """
    vector_literal = "[" + ",".join(f"{float(v):.8f}" for v in embedding) + "]"
    stmt = text(
        """
        SELECT photo_id, score FROM (
            SELECT DISTINCT ON (f.photo_id)
                   f.photo_id AS photo_id,
                   1 - (f.embedding <=> CAST(:q AS vector)) AS score
            FROM faces f
            JOIN photos p ON p.id = f.photo_id
            WHERE f.event_id = :event_id
              AND p.status = :ready
            ORDER BY f.photo_id, f.embedding <=> CAST(:q AS vector)
        ) best
        WHERE score >= :threshold
        ORDER BY score DESC
        LIMIT :limit
        """
    ).bindparams(
        bindparam("q", value=vector_literal),
        bindparam("event_id", value=event_id),
        bindparam("ready", value=PhotoStatus.READY.value),
        bindparam("threshold", value=float(threshold)),
        bindparam("limit", value=int(limit)),
    )
    return [(row.photo_id, float(row.score)) for row in db.execute(stmt)]


def _rank_numpy(
    db: Session, event_id: uuid.UUID, embedding: np.ndarray, threshold: float, limit: int
) -> list[tuple[uuid.UUID, float]]:
    """Exact brute-force search used when pgvector is not available."""
    rows = db.execute(
        select(Face.photo_id, Face.embedding)
        .join(Photo, Photo.id == Face.photo_id)
        .where(Face.event_id == event_id, Photo.status == PhotoStatus.READY)
    ).all()
    if not rows:
        return []

    query = np.asarray(embedding, dtype=np.float32)
    best: dict[uuid.UUID, float] = {}
    for photo_id, raw in rows:
        vec = np.asarray(raw, dtype=np.float32)
        if vec.shape != query.shape:
            continue
        score = float(np.dot(query, vec))
        if score > best.get(photo_id, -2.0):
            best[photo_id] = score

    ranked = [(pid, s) for pid, s in best.items() if s >= threshold]
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked[:limit]


def _load_matches(
    db: Session, photo_ids: list[uuid.UUID], scores: dict[uuid.UUID, float]
) -> list[MatchedPhoto]:
    if not photo_ids:
        return []
    photos = db.execute(select(Photo).where(Photo.id.in_(photo_ids))).scalars().all()
    by_id = {p.id: p for p in photos}
    return [
        MatchedPhoto(photo=by_id[pid], score=scores[pid]) for pid in photo_ids if pid in by_id
    ]
