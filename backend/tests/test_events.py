"""Event lifecycle and ownership isolation."""

from __future__ import annotations

import re
import uuid


def test_create_event_generates_code_and_url(client, photographer):
    r = client.post("/api/events", headers=photographer["headers"], json={
        "name": "Mohamed Wedding", "event_date": "2026-09-01", "location": "Nagore",
    })
    assert r.status_code == 201
    body = r.json()
    assert re.fullmatch(r"EVT-[A-Z0-9]{6}", body["event_code"])
    assert body["public_url"].endswith(f"/event/{body['event_code']}")
    assert body["status"] == "LIVE"


def test_event_codes_avoid_lookalike_characters(client, photographer):
    codes = []
    for i in range(12):
        r = client.post("/api/events", headers=photographer["headers"], json={"name": f"Event {i}"})
        codes.append(r.json()["event_code"])
    assert len(set(codes)) == len(codes)
    body = "".join(c.split("-")[1] for c in codes)
    assert not set(body) & set("O0I1L5SBZ")


def test_create_event_rejects_blank_name(client, photographer):
    r = client.post("/api/events", headers=photographer["headers"], json={"name": "  "})
    assert r.status_code == 422


def test_get_event_returns_stats(client, photographer, event):
    r = client.get(f"/api/events/{event['id']}", headers=photographer["headers"])
    assert r.status_code == 200
    stats = r.json()["stats"]
    assert stats["photos"] == 0 and stats["guests"] == 0


def test_list_events_is_newest_first(client, photographer, event):
    client.post("/api/events", headers=photographer["headers"], json={"name": "Later Event"})
    r = client.get("/api/events", headers=photographer["headers"])
    assert r.status_code == 200
    assert r.json()[0]["name"] == "Later Event"


def test_update_event(client, photographer, event):
    r = client.put(f"/api/events/{event['id']}", headers=photographer["headers"], json={
        "name": "Mohamed & Aisha Wedding", "status": "ARCHIVED",
    })
    assert r.status_code == 200
    assert r.json()["name"] == "Mohamed & Aisha Wedding"
    assert r.json()["status"] == "ARCHIVED"


def test_delete_event(client, photographer, event):
    assert client.delete(f"/api/events/{event['id']}", headers=photographer["headers"]).status_code == 200
    assert client.get(f"/api/events/{event['id']}", headers=photographer["headers"]).status_code == 404


def test_photographer_cannot_read_another_photographers_event(client, event, second_photographer):
    r = client.get(f"/api/events/{event['id']}", headers=second_photographer["headers"])
    # 404 rather than 403 so the API never confirms the event exists.
    assert r.status_code == 404


def test_photographer_cannot_update_another_photographers_event(client, event, second_photographer):
    r = client.put(f"/api/events/{event['id']}", headers=second_photographer["headers"],
                   json={"name": "Hijacked"})
    assert r.status_code == 404


def test_photographer_cannot_delete_another_photographers_event(client, event, second_photographer):
    assert client.delete(f"/api/events/{event['id']}",
                         headers=second_photographer["headers"]).status_code == 404


def test_event_list_is_scoped_to_owner(client, event, second_photographer):
    assert client.get("/api/events", headers=second_photographer["headers"]).json() == []


def test_unknown_event_id_is_404(client, photographer):
    r = client.get(f"/api/events/{uuid.uuid4()}", headers=photographer["headers"])
    assert r.status_code == 404


def test_dashboard_aggregates(client, photographer, event):
    r = client.get("/api/events/dashboard", headers=photographer["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["stats"]["total_events"] == 1
    assert body["stats"]["active_events"] == 1
    assert len(body["recent_events"]) == 1


def test_qr_endpoint_returns_png(client, photographer, event):
    r = client.get(f"/api/events/{event['id']}/qr", headers=photographer["headers"])
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_qr_download_sets_attachment_header(client, photographer, event):
    r = client.get(f"/api/events/{event['id']}/qr?download=true", headers=photographer["headers"])
    assert "attachment" in r.headers["content-disposition"]
    assert event["event_code"] in r.headers["content-disposition"]


def test_qr_encodes_the_public_event_url(client, photographer, event):
    """The QR must resolve to the guest page, not the dashboard."""
    import io
    import cv2
    import numpy as np
    from PIL import Image

    r = client.get(f"/api/events/{event['id']}/qr", headers=photographer["headers"])
    img = np.array(Image.open(io.BytesIO(r.content)).convert("RGB"))
    decoded, *_ = cv2.QRCodeDetector().detectAndDecode(cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    assert decoded.endswith(f"/event/{event['event_code']}")


def test_qr_requires_ownership(client, event, second_photographer):
    r = client.get(f"/api/events/{event['id']}/qr", headers=second_photographer["headers"])
    assert r.status_code == 404
