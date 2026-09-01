"""Create demo data.

    python -m scripts.seed              # photographer + event
    python -m scripts.seed --photos ~/Pictures/wedding
    python -m scripts.seed --reset      # delete the demo account first

Credentials created:

    demo@allbee.local / Demo@12345
    Event: ALLBEE Demo Wedding  (EVT-DEMO01)

Any photos supplied are uploaded through the same service the API uses, so
they get thumbnails, face detection and READY status exactly as a real upload
would. No fixtures, no shortcuts.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path

from sqlalchemy import select

from app.config import settings
from app.database import session_scope
from app.models import Event, EventStatus, User
from app.services.photos import DuplicatePhotoError, ingest_photo
from app.services.security import hash_password
from app.services.storage import storage
from app.services.tasks import task_queue

DEMO_EMAIL = "demo@allbee.local"
DEMO_PASSWORD = "Demo@12345"
DEMO_NAME = "Demo Photographer"
DEMO_EVENT_CODE = "EVT-DEMO01"
DEMO_EVENT_NAME = "ALLBEE Demo Wedding"


def reset(db) -> None:
    user = db.execute(select(User).where(User.email == DEMO_EMAIL)).scalar_one_or_none()
    if user is None:
        print("Nothing to reset.")
        return
    for event in list(user.events):
        storage.delete_event(event.event_code)
    db.delete(user)
    db.commit()
    print(f"Removed {DEMO_EMAIL} and its events.")


def seed(db, photo_dir: Path | None) -> None:
    user = db.execute(select(User).where(User.email == DEMO_EMAIL)).scalar_one_or_none()
    if user is None:
        user = User(name=DEMO_NAME, email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD))
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"Created photographer  {DEMO_EMAIL} / {DEMO_PASSWORD}")
    else:
        print(f"Photographer already exists  {DEMO_EMAIL}")

    event = db.execute(
        select(Event).where(Event.event_code == DEMO_EVENT_CODE)
    ).scalar_one_or_none()
    if event is None:
        event = Event(
            user_id=user.id,
            name=DEMO_EVENT_NAME,
            event_code=DEMO_EVENT_CODE,
            event_date=date(2026, 9, 1),
            location="Nagore",
            description="Seeded demo event. Scan the QR code to try the guest flow.",
            status=EventStatus.LIVE,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        print(f"Created event         {DEMO_EVENT_CODE}  {DEMO_EVENT_NAME}")
    else:
        print(f"Event already exists  {DEMO_EVENT_CODE}")

    storage.ensure_event_dirs(event.event_code)

    if photo_dir is not None:
        _import_photos(db, event, photo_dir)

    print()
    print("  Guest page:  " + settings.event_url(event.event_code))
    print("  Dashboard:   " + settings.public_base_url.rstrip("/") + "/dashboard")


def _import_photos(db, event: Event, photo_dir: Path) -> None:
    if not photo_dir.is_dir():
        print(f"Photo folder not found: {photo_dir}", file=sys.stderr)
        return

    candidates = sorted(
        p
        for p in photo_dir.rglob("*")
        if p.is_file() and p.suffix.lower().lstrip(".") in settings.extensions
    )
    if not candidates:
        print(f"No {'/'.join(sorted(settings.extensions))} files in {photo_dir}")
        return

    print(f"\nUploading {len(candidates)} photo(s) from {photo_dir} ...")
    added = skipped = failed = 0
    for path in candidates:
        try:
            ingest_photo(db, event, path.name, path.read_bytes())
            added += 1
        except DuplicatePhotoError:
            skipped += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ! {path.name}: {exc}")
        if (added + skipped + failed) % 25 == 0:
            print(f"  {added + skipped + failed}/{len(candidates)} ...")

    print(f"Uploaded {added}, skipped {skipped} duplicate(s), {failed} failed.")
    print("Waiting for face processing ...")
    while task_queue.pending > 0:
        time.sleep(0.25)
    print("Face processing complete.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed ALLBEE Instant demo data")
    parser.add_argument("--photos", type=Path, help="Folder of photos to upload into the event")
    parser.add_argument("--reset", action="store_true", help="Delete the demo account first")
    args = parser.parse_args(argv)

    db = session_scope()
    try:
        if args.reset:
            reset(db)
        seed(db, args.photos)
    finally:
        db.close()
        task_queue.shutdown(wait=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
