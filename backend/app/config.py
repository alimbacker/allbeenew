"""Application configuration.

Every tunable lives here and is read from the environment exactly once.
Nothing in the codebase is allowed to hardcode a threshold, a path or a limit --
import ``settings`` instead.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Core ---------------------------------------------------------------
    app_name: str = "ALLBEE Instant"
    environment: str = "development"
    debug: bool = True

    # ---- Database -----------------------------------------------------------
    database_url: str = "postgresql://allbee:allbee@localhost:5432/allbee"

    # ---- Auth ---------------------------------------------------------------
    jwt_secret: str = "change-this-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    # ---- Storage ------------------------------------------------------------
    storage_path: Path = BACKEND_ROOT / "storage"
    max_upload_size_mb: int = 25
    allowed_extensions: str = "jpg,jpeg,png,webp"
    thumbnail_max_edge: int = 640
    thumbnail_quality: int = 82

    # ---- Face recognition ---------------------------------------------------
    # ``arcface`` = SCRFD detector + ArcFace embeddings run through onnxruntime.
    # ``opencv``  = YuNet detector + SFace embeddings run through cv2.
    face_engine: str = "arcface"
    face_model_dir: Path = BACKEND_ROOT / "models"
    face_model_pack: str = "buffalo_l"
    face_detect_size: int = 640
    face_detect_threshold: float = 0.5
    face_min_size: int = 32

    # Cosine similarity in [-1, 1]. See docs/FACE_RECOGNITION.md for calibration.
    face_match_threshold: float = 0.38
    face_max_results: int = 300

    # ---- Background processing ---------------------------------------------
    worker_concurrency: int = 2

    # ---- Public URLs --------------------------------------------------------
    public_base_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"

    # ---- Rate limiting ------------------------------------------------------
    search_rate_limit: int = 10
    search_rate_window_seconds: int = 60
    upload_rate_limit: int = 600
    upload_rate_window_seconds: int = 60

    # ---- Privacy ------------------------------------------------------------
    # 0 disables automatic cleanup. Nothing is ever deleted unless set > 0.
    guest_data_retention_days: int = 0

    # ---- Validators ---------------------------------------------------------
    @field_validator("database_url")
    @classmethod
    def _normalise_db_url(cls, v: str) -> str:
        """Pin the driver so a plain ``postgresql://`` URL works with psycopg 3."""
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+psycopg://", 1)
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+psycopg://", 1)
        return v

    @field_validator("storage_path", "face_model_dir")
    @classmethod
    def _absolute(cls, v: Path) -> Path:
        p = Path(v).expanduser()
        return p if p.is_absolute() else (BACKEND_ROOT / p).resolve()

    # ---- Derived ------------------------------------------------------------
    @property
    def extensions(self) -> set[str]:
        return {e.strip().lower().lstrip(".") for e in self.allowed_extensions.split(",") if e.strip()}

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def embedding_dim(self) -> int:
        """Vector width produced by the selected engine."""
        return 128 if self.face_engine == "opencv" else 512

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    def event_url(self, event_code: str) -> str:
        return f"{self.public_base_url.rstrip('/')}/event/{event_code}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
