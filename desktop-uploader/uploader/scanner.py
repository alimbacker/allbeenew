"""Folder scanning and progress state — deliberately free of Qt.

Keeping this layer independent of PySide6 means the part with the actual rules
(what counts as an image, when a file has finished being written) can be tested
without a GUI toolkit or a display.

Polling rather than filesystem events, on purpose: tethered-capture folders and
camera cards are often on network shares or removable media where inotify and
ReadDirectoryChangesW are unreliable or silently unsupported. A scan every few
seconds is cheap and never misses a file.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}

# A file must hold the same size across two scans this far apart before it is
# considered complete. Stops a 40 MB write being uploaded half-finished.
SETTLE_SECONDS = 1.5

MAX_ATTEMPTS = 3


@dataclass
class Progress:
    detected: int = 0
    uploaded: int = 0
    duplicates: int = 0
    failed: int = 0
    queued: int = 0
    current: str = ""
    connected: bool = True
    message: str = ""
    failures: list[str] = field(default_factory=list)


class FolderScanner:
    """Finds image files that have stopped growing."""

    def __init__(self, folder: Path, settle_seconds: float = SETTLE_SECONDS) -> None:
        self.folder = Path(folder)
        self.settle_seconds = settle_seconds
        self._sizes: dict[Path, tuple[int, float]] = {}

    def scan(self) -> list[Path]:
        try:
            candidates = [
                path
                for path in self.folder.rglob("*")
                if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
            ]
        except OSError:
            # The card was pulled or the share dropped: report nothing this
            # round and try again on the next tick.
            return []

        ready: list[Path] = []
        now = time.monotonic()
        for path in candidates:
            try:
                size = path.stat().st_size
            except OSError:
                continue
            previous = self._sizes.get(path)
            if previous is None or previous[0] != size:
                self._sizes[path] = (size, now)
                continue
            if now - previous[1] >= self.settle_seconds and size > 0:
                ready.append(path)
        return sorted(ready)
