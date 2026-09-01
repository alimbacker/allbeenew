"""Registration, login and access control."""

from __future__ import annotations

import uuid


def test_register_returns_token_and_user(client):
    email = f"new-{uuid.uuid4().hex[:8]}@allbee.test"
    r = client.post("/api/auth/register", json={
        "name": "Nadia Farouk", "email": email,
        "password": "Instant123", "confirm_password": "Instant123",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == email
    assert "password" not in str(body).lower() or "password_hash" not in body["user"]


def test_register_rejects_mismatched_confirmation(client):
    r = client.post("/api/auth/register", json={
        "name": "Nadia", "email": "n@allbee.test",
        "password": "Instant123", "confirm_password": "Instant999",
    })
    assert r.status_code == 422
    assert "match" in r.json()["detail"].lower()


def test_register_rejects_short_password(client):
    r = client.post("/api/auth/register", json={
        "name": "Nadia", "email": "n2@allbee.test",
        "password": "abc", "confirm_password": "abc",
    })
    assert r.status_code == 422


def test_register_rejects_invalid_email(client):
    r = client.post("/api/auth/register", json={
        "name": "Nadia", "email": "not-an-email",
        "password": "Instant123", "confirm_password": "Instant123",
    })
    assert r.status_code == 422


def test_register_rejects_duplicate_email(client, photographer):
    r = client.post("/api/auth/register", json={
        "name": "Impostor", "email": photographer["email"],
        "password": "Instant123", "confirm_password": "Instant123",
    })
    assert r.status_code == 409


def test_email_is_case_insensitive(client, photographer):
    r = client.post("/api/auth/login", json={
        "email": photographer["email"].upper(), "password": photographer["password"],
    })
    assert r.status_code == 200


def test_login_succeeds(client, photographer):
    r = client.post("/api/auth/login", json={
        "email": photographer["email"], "password": photographer["password"],
    })
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_login_rejects_wrong_password(client, photographer):
    r = client.post("/api/auth/login", json={
        "email": photographer["email"], "password": "WrongPassword1",
    })
    assert r.status_code == 401
    # Same message as an unknown account: no user enumeration.
    assert r.json()["detail"] == "Incorrect email or password"


def test_login_rejects_unknown_email(client):
    r = client.post("/api/auth/login", json={
        "email": "nobody@allbee.test", "password": "Instant123",
    })
    assert r.status_code == 401
    assert r.json()["detail"] == "Incorrect email or password"


def test_password_is_hashed_not_stored(db, client, photographer):
    from app.models import User
    from sqlalchemy import select

    user = db.execute(select(User).where(User.email == photographer["email"])).scalar_one()
    assert user.password_hash != photographer["password"]
    assert user.password_hash.startswith("$2b$")


def test_me_returns_current_user(client, photographer):
    r = client.get("/api/auth/me", headers=photographer["headers"])
    assert r.status_code == 200
    assert r.json()["email"] == photographer["email"]


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_rejects_garbage_token(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401


def test_expired_token_is_rejected(client, photographer):
    from app.services.security import create_access_token

    stale = create_access_token(photographer["user"]["id"], expires_minutes=-5)
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {stale}"})
    assert r.status_code == 401


def test_protected_endpoints_require_auth(client):
    for method, path in [
        ("get", "/api/events"),
        ("post", "/api/events"),
        ("get", "/api/events/dashboard"),
    ]:
        assert getattr(client, method)(path).status_code == 401
