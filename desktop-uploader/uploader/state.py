"""Local state for the uploader.

Two jobs:

* Remember which files have already been sent, per event, so restarting the
  app does not re-upload a whole wedding. Keyed by content hash rather than by
  path, so renaming or moving a file is not treated as a new photo.
* Remember the last-used server, event and folder so the photographer does not
  reconfigure at every venue.

Kept in a JSON file under the user's config directory. SQLite would be
overkill for a few thousand hashes and would make the file harder to inspect
when something goes wrong on site.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path


def config_dir() -> Path:
    """Per-user config location, following each platform's convention."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif os.sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = base / "ALLBEE Instant Uploader"
    path.mkdir(parents=True, exist_ok=True)
    return path


def file_hash(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


class UploaderState:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (config_dir() / "state.json")
        self._data: dict = {"settings": {}, "uploaded": {}}
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                # A corrupt state file must not stop the photographer working;
                # worst case we re-check hashes against the server.
                self._data = {"settings": {}, "uploaded": {}}
        self._data.setdefault("settings", {})
        self._data.setdefault("uploaded", {})

    def save(self) -> None:
        # Atomic replace: the app may be killed mid-event.
        handle, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2)
            os.replace(tmp, self.path)
        except OSError:
            Path(tmp).unlink(missing_ok=True)

    # -- settings ----------------------------------------------------------
    def get(self, key: str, default=None):
        return self._data["settings"].get(key, default)

    def set(self, key: str, value) -> None:
        self._data["settings"][key] = value
        self.save()

    # -- upload ledger -----------------------------------------------------
    def is_uploaded(self, event_id: str, digest: str) -> bool:
        return digest in self._data["uploaded"].get(event_id, {})

    def mark_uploaded(self, event_id: str, digest: str, filename: str) -> None:
        self._data["uploaded"].setdefault(event_id, {})[digest] = filename
        self.save()

    def uploaded_count(self, event_id: str) -> int:
        return len(self._data["uploaded"].get(event_id, {}))

    def forget_event(self, event_id: str) -> None:
        self._data["uploaded"].pop(event_id, None)
        self.save()
