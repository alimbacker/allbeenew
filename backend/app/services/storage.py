"""Filesystem storage.

Everything the app writes goes through this class. Two consequences worth
keeping:

* The database only ever stores *relative* POSIX paths, so moving the storage
  directory to another server (or another mount) needs no data migration --
  only a change to STORAGE_PATH.
* Every path is validated against the storage root before use, so a crafted
  DB value or filename cannot escape the tree.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path, PurePosixPath

from app.config import settings
from app.utils.files import is_within, safe_relative

logger = logging.getLogger(__name__)


class LocalStorage:
    """Local-disk implementation of the storage contract.

    Swapping in a different backend (NFS, MinIO, another server over SSHFS)
    means implementing these same five methods; nothing else changes.
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root or settings.storage_path)
        self.root.mkdir(parents=True, exist_ok=True)

    # -- path helpers ------------------------------------------------------
    def event_dir(self, event_code: str) -> PurePosixPath:
        return PurePosixPath("events") / event_code

    def relative_path(self, event_code: str, kind: str, filename: str) -> str:
        """Build the relative path stored in the database."""
        if kind not in {"originals", "thumbnails", "selfies"}:
            raise ValueError(f"Unknown storage kind {kind!r}")
        return str(self.event_dir(event_code) / kind / filename)

    def absolute(self, relative: str) -> Path:
        """Resolve a stored relative path to a real path inside the root."""
        rel = safe_relative(relative)
        target = self.root / Path(*rel.parts)
        if not is_within(self.root, target.parent if not target.exists() else target):
            raise ValueError(f"Path escapes storage root: {relative!r}")
        return target

    # -- operations --------------------------------------------------------
    def ensure_event_dirs(self, event_code: str) -> None:
        for kind in ("originals", "thumbnails", "selfies"):
            (self.root / "events" / event_code / kind).mkdir(parents=True, exist_ok=True)

    def write_bytes(self, relative: str, data: bytes) -> Path:
        target = self.absolute(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Write to a sibling temp file then rename, so a crashed upload never
        # leaves a half-written JPEG that the worker would try to process.
        tmp = target.with_suffix(target.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(target)
        return target

    def read_bytes(self, relative: str) -> bytes:
        return self.absolute(relative).read_bytes()

    def exists(self, relative: str) -> bool:
        try:
            return self.absolute(relative).exists()
        except ValueError:
            return False

    def delete(self, relative: str) -> bool:
        try:
            target = self.absolute(relative)
        except ValueError:
            logger.warning("Refusing to delete unsafe path %r", relative)
            return False
        if target.exists():
            target.unlink()
            return True
        return False

    def delete_event(self, event_code: str) -> None:
        target = self.root / "events" / event_code
        if is_within(self.root, target) and target.exists():
            shutil.rmtree(target, ignore_errors=True)

    def size(self, relative: str) -> int:
        return self.absolute(relative).stat().st_size


storage = LocalStorage()
