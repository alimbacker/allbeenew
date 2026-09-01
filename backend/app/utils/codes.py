"""Event code generation.

Codes are read aloud, typed on phones and printed on signage, so the alphabet
excludes characters that are easy to confuse: 0/O, 1/I/L, 5/S, 8/B.
"""

from __future__ import annotations

import secrets

ALPHABET = "ACDEFGHJKMNPQRTUVWXY2346789"
PREFIX = "EVT"
LENGTH = 6


def generate_event_code() -> str:
    """Return a code like ``EVT-8F42K9``."""
    body = "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))
    return f"{PREFIX}-{body}"


def normalise_event_code(code: str) -> str:
    """Accept user-typed codes in any case, with or without the dash."""
    cleaned = "".join(ch for ch in code.upper() if ch.isalnum())
    if cleaned.startswith(PREFIX) and len(cleaned) > len(PREFIX):
        return f"{PREFIX}-{cleaned[len(PREFIX):]}"
    return cleaned
