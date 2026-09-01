"""Thin HTTP client for the ALLBEE API."""

from __future__ import annotations

from pathlib import Path

import requests


class ApiError(Exception):
    def __init__(self, message: str, status: int = 0) -> None:
        self.status = status
        super().__init__(message)


class AllbeeClient:
    def __init__(self, base_url: str, timeout: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token: str | None = None
        self.session = requests.Session()

    # -- helpers -----------------------------------------------------------
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def _handle(self, response: requests.Response) -> dict:
        if response.status_code == 401:
            raise ApiError("Session expired. Sign in again.", 401)
        if not response.ok:
            message = f"Request failed ({response.status_code})"
            try:
                detail = response.json().get("detail")
                if isinstance(detail, str):
                    message = detail
                elif isinstance(detail, dict):
                    message = detail.get("message", message)
            except ValueError:
                pass
            raise ApiError(message, response.status_code)
        return response.json()

    # -- endpoints ---------------------------------------------------------
    def ping(self) -> dict:
        try:
            return self._handle(self.session.get(f"{self.base_url}/health", timeout=10))
        except requests.RequestException as exc:
            raise ApiError(f"Can't reach {self.base_url}") from exc

    def login(self, email: str, password: str) -> dict:
        try:
            data = self._handle(
                self.session.post(
                    f"{self.base_url}/api/auth/login",
                    json={"email": email, "password": password},
                    timeout=30,
                )
            )
        except requests.RequestException as exc:
            raise ApiError(f"Can't reach {self.base_url}") from exc
        self.token = data["access_token"]
        return data

    def events(self) -> list[dict]:
        try:
            return self._handle(
                self.session.get(
                    f"{self.base_url}/api/events", headers=self._headers(), timeout=30
                )
            )
        except requests.RequestException as exc:
            raise ApiError("Could not load events") from exc

    def upload(self, event_id: str, path: Path) -> dict:
        """Upload one file. Returns the per-file result from the API."""
        try:
            with path.open("rb") as handle:
                response = self.session.post(
                    f"{self.base_url}/api/events/{event_id}/photos",
                    headers=self._headers(),
                    files={"files": (path.name, handle, "application/octet-stream")},
                    timeout=self.timeout,
                )
        except requests.RequestException as exc:
            raise ApiError(f"Upload failed: {exc.__class__.__name__}") from exc

        body = self._handle(response)
        results = body.get("results") or []
        return results[0] if results else {"status": "rejected", "error": "Empty response"}
