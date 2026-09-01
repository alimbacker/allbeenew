"""ALLBEE Instant API."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.face.engine import engine_status, get_engine
from app.routes import auth, events, photos, public
from app.schemas.common import HealthResponse
from app.services.live import live_bus
from app.services.storage import storage
from app.services.tasks import task_queue

VERSION = "1.0.0"

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
logger = logging.getLogger("allbee")

DESCRIPTION = """
Deliver event photos to guests while the event is still running.

**Capture. Match. Deliver.**

A photographer creates an event and uploads photos continuously. Each photo is
thumbnailed and scanned for faces in the background. Guests scan the event QR
code, submit one selfie, and get back every photo they appear in.

### How to use these docs
1. `POST /api/auth/register` or `/api/auth/login`, then click **Authorize** and
   paste the `access_token`.
2. `POST /api/events` to create an event.
3. `POST /api/events/{event_id}/photos` to upload.
4. Everything under **Guest** works with no token at all -- only the event code.

### Notes
* Face matching runs locally. No image is sent to any third-party service.
* Photo bytes are served only through the guarded endpoints in this API; the
  storage directory is never exposed by the web server.
"""

TAGS = [
    {"name": "Authentication", "description": "Photographer accounts and JWTs."},
    {"name": "Events", "description": "Create and manage events, and generate QR codes."},
    {"name": "Photos", "description": "Upload, list and delete photos."},
    {"name": "Guest", "description": "No-login endpoints reached through an event code."},
    {"name": "System", "description": "Health and readiness."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    live_bus.bind_loop(asyncio.get_running_loop())
    storage.root.mkdir(parents=True, exist_ok=True)
    logger.info("Storage root: %s", storage.root)

    # Load the face models off the event loop so the first guest search is not
    # the request that pays the several-second model load.
    async def warm_up() -> None:
        try:
            eng = await asyncio.to_thread(get_engine)
            logger.info("Face engine ready: %s (%d-d)", eng.name, eng.dim)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Face engine not ready: %s. Uploads will still be stored; run "
                "`python -m app.face.download` then POST .../photos/reprocess.",
                exc,
            )

    task = asyncio.create_task(warm_up())
    try:
        yield
    finally:
        task.cancel()
        task_queue.shutdown(wait=False)


app = FastAPI(
    title="ALLBEE Instant",
    summary="Capture. Match. Deliver. — On the Spot.",
    description=DESCRIPTION,
    version=VERSION,
    openapi_tags=TAGS,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Flatten Pydantic errors into one readable sentence for the UI.

    ``exc.errors()`` can carry the original exception object under ``ctx``,
    which is not JSON-serialisable, so each entry is rebuilt from plain values
    rather than passed through.
    """
    summary: list[str] = []
    errors: list[dict] = []
    for err in exc.errors():
        location = [str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path")]
        field = ".".join(location)
        message = str(err.get("msg", "Invalid value"))
        summary.append(f"{field}: {message}" if field else message)
        errors.append({"field": field, "message": message, "type": str(err.get("type", ""))})

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "; ".join(summary) or "Invalid request", "errors": errors},
    )


app.include_router(auth.router)
app.include_router(events.router)
app.include_router(photos.router)
app.include_router(public.router)


@app.get("/", tags=["System"], summary="Service banner")
def root() -> dict:
    return {
        "name": "ALLBEE Instant",
        "tagline": "Capture. Match. Deliver.",
        "version": VERSION,
        "docs": "/docs",
    }


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health check",
)
def health() -> HealthResponse:
    """Reports database connectivity, face engine state and worker backlog.

    Returns 200 even when the face engine has not loaded: photos can still be
    uploaded and stored, they simply queue until models are available.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        database=db_ok,
        face_engine=engine_status(),
        pending_tasks=task_queue.pending,
        version=VERSION,
    )
