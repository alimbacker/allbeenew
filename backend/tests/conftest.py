"""Shared test fixtures.

Two things make this suite fast and hermetic:

* SQLite + a temporary storage directory, so no server and no cleanup.
* A deterministic stand-in for the face engine. Real ONNX models are ~190 MB
  and several seconds to load, which is the wrong trade for unit tests. The
  fake obeys the same ``FaceEngine`` protocol, so it exercises the real
  ingestion, storage, ranking and API code -- only the pixels-to-vector step is
  substituted.

`test_face_engine.py` covers the real models and skips when they are absent.
"""

from __future__ import annotations

import io
import os
import tempfile
import uuid
from pathlib import Path

# Must be set before any app module reads settings.
_TMP = Path(tempfile.mkdtemp(prefix="allbee-tests-"))
os.environ.update(
    DATABASE_URL=f"sqlite:///{_TMP / 'test.db'}",
    STORAGE_PATH=str(_TMP / "storage"),
    JWT_SECRET="test-secret-not-for-production",
    FACE_MATCH_THRESHOLD="0.5",
    MAX_UPLOAD_SIZE_MB="5",
    SEARCH_RATE_LIMIT="1000",
    UPLOAD_RATE_LIMIT="100000",
    WORKER_CONCURRENCY="1",
    ENVIRONMENT="test",
)

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.database import SessionLocal, engine  # noqa: E402
from app.face.base import BoundingBox, DetectedFace  # noqa: E402
from app.face.engine import set_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.services.rate_limit import search_limiter, upload_limiter  # noqa: E402
from app.services.storage import storage  # noqa: E402

# Distinct, saturated colours standing in for distinct people.
PERSON_COLOURS = {
    1: (220, 40, 40),
    2: (40, 200, 90),
    3: (50, 90, 230),
    4: (230, 190, 40),
    5: (170, 60, 210),
}
BACKGROUND = (245, 245, 245)


# --------------------------------------------------------------------------
# Image factories
# --------------------------------------------------------------------------
def make_photo(people: list[int], size: tuple[int, int] = (640, 400), fmt: str = "JPEG") -> bytes:
    """An image containing one colour band per person.

    The fake engine reads those bands back as faces, so `make_photo([1, 2])`
    behaves like a real photo with two identifiable guests in it.
    """
    width, height = size
    img = Image.new("RGB", size, BACKGROUND)
    pixels = img.load()
    if people:
        band = width // len(people)
        for idx, person in enumerate(people):
            colour = PERSON_COLOURS[person]
            x0 = idx * band
            x1 = width if idx == len(people) - 1 else (idx + 1) * band
            for x in range(x0 + 10, max(x0 + 11, x1 - 10)):
                for y in range(height // 4, height * 3 // 4):
                    pixels[x, y] = colour
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def make_selfie(person: int) -> bytes:
    return make_photo([person], size=(320, 320))


def make_empty_photo() -> bytes:
    """A valid image with nobody in it."""
    return make_photo([], size=(320, 240))


def make_corrupt_file() -> bytes:
    return b"this is definitely not an image" * 8


# --------------------------------------------------------------------------
# Fake face engine
# --------------------------------------------------------------------------
def _embedding_for(person: int, dim: int = 512) -> np.ndarray:
    """A stable unit vector per person id."""
    rng = np.random.default_rng(seed=1000 + person)
    vec = rng.normal(size=dim).astype(np.float32)
    return vec / np.linalg.norm(vec)


class FakeFaceEngine:
    """Recovers person ids from colour bands and emits stable embeddings."""

    name = "fake"
    dim = 512

    def detect(self, image_bgr: np.ndarray) -> list[DetectedFace]:
        height, width = image_bgr.shape[:2]
        found: list[DetectedFace] = []
        for person, (r, g, b) in PERSON_COLOURS.items():
            target = np.array([b, g, r], dtype=np.int16)  # OpenCV order
            mask = (np.abs(image_bgr.astype(np.int16) - target).sum(axis=2) < 40)
            if mask.sum() < 200:
                continue
            ys, xs = np.nonzero(mask)
            found.append(
                DetectedFace(
                    box=BoundingBox(
                        x=int(xs.min()),
                        y=int(ys.min()),
                        width=int(xs.max() - xs.min()),
                        height=int(ys.max() - ys.min()),
                    ),
                    score=0.99,
                    embedding=_embedding_for(person, self.dim),
                )
            )
        found.sort(key=lambda f: f.box.x)
        return found


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def _face_engine():
    set_engine(FakeFaceEngine())
    yield
    set_engine(None)


@pytest.fixture(autouse=True)
def _clean_state():
    """Fresh schema, fresh storage and fresh rate-limit buckets per test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    search_limiter.reset()
    upload_limiter.reset()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> TestClient:
    # Entering the context manager runs lifespan, which binds the live bus.
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def photographer(client: TestClient) -> dict:
    """A registered, signed-in photographer with ready-to-use auth headers."""
    email = f"pat-{uuid.uuid4().hex[:8]}@allbee.test"
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Pat Rivera",
            "email": email,
            "password": "Instant123",
            "confirm_password": "Instant123",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return {
        "email": email,
        "password": "Instant123",
        "token": body["access_token"],
        "user": body["user"],
        "headers": {"Authorization": f"Bearer {body['access_token']}"},
    }


@pytest.fixture
def second_photographer(client: TestClient) -> dict:
    email = f"sam-{uuid.uuid4().hex[:8]}@allbee.test"
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Sam Okafor",
            "email": email,
            "password": "Instant456",
            "confirm_password": "Instant456",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return {"headers": {"Authorization": f"Bearer {body['access_token']}"}}


@pytest.fixture
def event(client: TestClient, photographer: dict) -> dict:
    response = client.post(
        "/api/events",
        headers=photographer["headers"],
        json={
            "name": "Mohamed Wedding",
            "event_date": "2026-09-01",
            "location": "Nagore",
            "description": "Reception and dinner",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def upload(client: TestClient):
    """Upload photos and wait for background face processing to finish."""

    def _upload(event_id: str, headers: dict, files: list[tuple[str, bytes]]) -> dict:
        response = client.post(
            f"/api/events/{event_id}/photos",
            headers=headers,
            files=[("files", (name, data, "image/jpeg")) for name, data in files],
        )
        _drain_workers()
        return response.json() if response.headers.get("content-type", "").startswith(
            "application/json"
        ) else {"status_code": response.status_code}

    return _upload


def _drain_workers(timeout: float = 30.0) -> None:
    """Block until the background queue is empty."""
    import time

    from app.services.tasks import task_queue

    deadline = time.monotonic() + timeout
    while task_queue.pending > 0 and time.monotonic() < deadline:
        time.sleep(0.02)
    time.sleep(0.05)


@pytest.fixture
def drain():
    return _drain_workers


@pytest.fixture
def storage_root() -> Path:
    return storage.root
