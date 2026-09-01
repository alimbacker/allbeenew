"""Filename sanitising, hashing and path-traversal protection."""

from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid
from pathlib import Path, PurePosixPath

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(name: str, fallback: str = "photo.jpg") -> str:
    """Reduce an uploaded filename to something safe to store and display.

    Drops directory components, folds to ASCII, and replaces anything a shell
    or path parser might interpret. The stem and the extension are cleaned
    separately: stripping the whole string at once would turn ``".jpg"`` into
    ``"jpg"``, silently losing the extension that decides how the file is
    stored and served.
    """
    if not name:
        return fallback

    # Basename under both separators: a Windows client may send the filename
    # as "D:\\Wedding\\IMG_0001.JPG".
    base = name.replace("\\", "/").split("/")[-1]
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    base = _UNSAFE.sub("_", base)

    stem, separator, ext = base.rpartition(".")
    if not separator:
        stem, ext = base, ""

    # Leading dots and dashes are stripped so the result can never become a
    # hidden file or be read as a command-line flag.
    stem = stem.strip("._-")
    ext = ext.strip("._-")

    if not stem and not ext:
        return fallback
    if not stem:
        stem = PurePosixPath(fallback).stem

    result = f"{stem}.{ext}" if ext else stem
    return result[:200]


def extension_of(name: str) -> str:
    return Path(name).suffix.lower().lstrip(".")


def unique_stored_name(original: str) -> str:
    """A collision-proof on-disk name that keeps the original extension."""
    ext = extension_of(original) or "jpg"
    return f"{uuid.uuid4().hex}.{ext}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def is_within(root: Path, candidate: Path) -> bool:
    """True when ``candidate`` resolves inside ``root``.

    The last line of defence against path traversal: every read and write goes
    through this before touching the filesystem.
    """
    try:
        root_r = Path(root).resolve()
        cand_r = Path(candidate).resolve()
    except (OSError, RuntimeError):
        return False
    return cand_r == root_r or root_r in cand_r.parents


def safe_relative(rel: str) -> PurePosixPath:
    """Validate a DB-stored relative path before joining it to the storage root."""
    p = PurePosixPath(str(rel).replace("\\", "/"))
    if p.is_absolute() or any(part == ".." for part in p.parts):
        raise ValueError(f"Unsafe relative path: {rel!r}")
    return p
