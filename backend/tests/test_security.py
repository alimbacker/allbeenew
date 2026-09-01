"""Storage path safety and filename handling."""

from __future__ import annotations

import pytest

from app.services.storage import LocalStorage
from app.utils.codes import generate_event_code, normalise_event_code
from app.utils.files import is_within, safe_relative, sanitize_filename


@pytest.mark.parametrize("raw", [
    "../../../etc/passwd",
    "..\\..\\windows\\system32\\config",
    "/etc/shadow",
    "events/../../secret.jpg",
])
def test_traversal_paths_are_refused(raw):
    with pytest.raises(ValueError):
        safe_relative(raw)


def test_storage_refuses_to_resolve_outside_root(tmp_path):
    store = LocalStorage(tmp_path)
    with pytest.raises(ValueError):
        store.absolute("../escaped.jpg")


def test_storage_resolves_valid_relative_path(tmp_path):
    store = LocalStorage(tmp_path)
    resolved = store.absolute("events/EVT-ABC123/originals/photo.jpg")
    assert is_within(tmp_path, resolved)


def test_storage_delete_refuses_unsafe_path(tmp_path):
    assert LocalStorage(tmp_path).delete("../../etc/passwd") is False


@pytest.mark.parametrize("raw,expected", [
    ("IMG_0001.JPG", "IMG_0001.JPG"),
    ("../../etc/passwd", "passwd"),
    ("D:\\Wedding\\IMG_2.jpg", "IMG_2.jpg"),
    ("photo;rm -rf /.jpg", "photo.jpg"),   # everything before "/" is a directory
    (".bashrc", "photo.bashrc"),           # never produce a hidden file
    ("", "photo.jpg"),
    ("...", "photo.jpg"),
])
def test_filename_sanitising(raw, expected):
    assert sanitize_filename(raw) == expected


def test_event_code_normalisation():
    code = generate_event_code()
    assert normalise_event_code(code.lower()) == code
    assert normalise_event_code(code.replace("-", "")) == code


def test_jwt_roundtrip_and_tampering():
    from app.services.security import create_access_token, decode_access_token

    token = create_access_token("abc-123")
    assert decode_access_token(token)["sub"] == "abc-123"
    assert decode_access_token(token[:-2] + "xy") is None
    assert decode_access_token("garbage") is None


def test_password_hashing_is_salted():
    from app.services.security import hash_password, verify_password

    a, b = hash_password("Instant123"), hash_password("Instant123")
    assert a != b  # different salts
    assert verify_password("Instant123", a) and verify_password("Instant123", b)
    assert not verify_password("Instant124", a)


def test_health_endpoint(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["database"] is True
