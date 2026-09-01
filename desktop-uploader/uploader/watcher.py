"""Upload worker thread.

Owns the scan/upload loop and reports progress to the UI. The scanning rules
live in ``uploader.scanner`` so they can be tested without Qt.
"""

from __future__ import annotations

import time
from pathlib import Path
from queue import Empty, Queue

from PySide6.QtCore import QObject, QThread, Signal

from uploader.client import AllbeeClient, ApiError
from uploader.scanner import MAX_ATTEMPTS, FolderScanner, Progress
from uploader.state import UploaderState, file_hash

class UploadWorker(QObject):
    """Owns the scan/upload loop. Lives on its own QThread."""

    progress = Signal(Progress)
    log = Signal(str)

    def __init__(
        self,
        client: AllbeeClient,
        state: UploaderState,
        event_id: str,
        folder: Path,
        poll_seconds: float = 3.0,
    ) -> None:
        super().__init__()
        self.client = client
        self.state = state
        self.event_id = event_id
        self.folder = Path(folder)
        self.poll_seconds = poll_seconds

        self._queue: Queue[Path] = Queue()
        self._seen: set[Path] = set()
        self._attempts: dict[Path, int] = {}
        self._running = False
        self._paused = False
        self._scanner = FolderScanner(self.folder)
        self.stats = Progress(uploaded=state.uploaded_count(event_id))

    # -- control -----------------------------------------------------------
    def stop(self) -> None:
        self._running = False

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        self.stats.message = "Paused" if paused else ""
        self.progress.emit(self.stats)

    def retry_failed(self) -> None:
        """Requeue everything that failed, resetting its attempt counter."""
        retried = 0
        for path, attempts in list(self._attempts.items()):
            if attempts >= MAX_ATTEMPTS and path.exists():
                self._attempts[path] = 0
                self._queue.put(path)
                retried += 1
        if retried:
            self.stats.failed = max(0, self.stats.failed - retried)
            self.stats.failures.clear()
            self.log.emit(f"Requeued {retried} failed upload(s)")

    # -- main loop ---------------------------------------------------------
    def run(self) -> None:
        self._running = True
        self.log.emit(f"Watching {self.folder}")
        last_scan = 0.0

        while self._running:
            if time.monotonic() - last_scan >= self.poll_seconds:
                self._enqueue_new()
                last_scan = time.monotonic()

            if self._paused:
                QThread.msleep(200)
                continue

            try:
                path = self._queue.get(timeout=0.4)
            except Empty:
                continue

            self._upload(path)
            self.stats.queued = self._queue.qsize()
            self.progress.emit(self.stats)

        self.log.emit("Stopped")

    def _enqueue_new(self) -> None:
        for path in self._scanner.scan():
            if path in self._seen:
                continue
            self._seen.add(path)
            self.stats.detected += 1
            try:
                digest = file_hash(path)
            except OSError:
                continue
            # Already sent in an earlier session: skip without touching the network.
            if self.state.is_uploaded(self.event_id, digest):
                self.stats.duplicates += 1
                continue
            self._queue.put(path)
        self.stats.queued = self._queue.qsize()
        self.progress.emit(self.stats)

    def _upload(self, path: Path) -> None:
        self.stats.current = path.name
        self.progress.emit(self.stats)
        attempt = self._attempts.get(path, 0) + 1
        self._attempts[path] = attempt

        try:
            result = self.client.upload(self.event_id, path)
            self.stats.connected = True
            status = result.get("status")

            if status in ("uploaded", "duplicate"):
                try:
                    self.state.mark_uploaded(self.event_id, file_hash(path), path.name)
                except OSError:
                    pass
                if status == "uploaded":
                    self.stats.uploaded += 1
                    self.log.emit(f"Uploaded {path.name}")
                else:
                    self.stats.duplicates += 1
                    self.log.emit(f"Already on the server: {path.name}")
            else:
                # Rejected by the server (bad file, too large). Retrying will
                # not help, so it is recorded as failed immediately.
                self._attempts[path] = MAX_ATTEMPTS
                self.stats.failed += 1
                reason = result.get("error", "rejected")
                self.stats.failures.append(f"{path.name}: {reason}")
                self.log.emit(f"Rejected {path.name} — {reason}")

        except ApiError as exc:
            if exc.status == 401:
                self.stats.connected = False
                self.stats.message = "Signed out. Sign in again to resume."
                self._running = False
                self.log.emit("Session expired")
                return
            if attempt < MAX_ATTEMPTS:
                # Transient: put it back with a short backoff.
                self.log.emit(f"Retry {attempt}/{MAX_ATTEMPTS} for {path.name} — {exc}")
                QThread.msleep(int(1000 * attempt))
                self._queue.put(path)
            else:
                self.stats.failed += 1
                self.stats.connected = False
                self.stats.failures.append(f"{path.name}: {exc}")
                self.log.emit(f"Gave up on {path.name} — {exc}")
        finally:
            self.stats.current = ""
