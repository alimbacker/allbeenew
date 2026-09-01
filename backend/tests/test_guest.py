"""The guest journey: public event, gallery, selfie search, download."""

from __future__ import annotations

import uuid

from conftest import make_corrupt_file, make_empty_photo, make_photo, make_selfie


def _seed_gallery(client, photographer, event, upload):
    """Three photos: person 1 alone, 1+2 together, and 3 alone."""
    return upload(event["id"], photographer["headers"], [
        ("solo1.jpg", make_photo([1], size=(600, 400))),
        ("group12.jpg", make_photo([1, 2], size=(620, 400))),
        ("solo3.jpg", make_photo([3], size=(640, 400))),
    ])


# -- public event ----------------------------------------------------------
def test_public_event_page(client, event, photographer, upload):
    _seed_gallery(client, photographer, event, upload)
    r = client.get(f"/api/public/events/{event['event_code']}")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Mohamed Wedding"
    assert body["photo_count"] == 3
    assert body["is_live"] is True


def test_public_event_needs_no_auth(client, event):
    assert client.get(f"/api/public/events/{event['event_code']}").status_code == 200


def test_event_code_is_case_insensitive(client, event):
    lower = event["event_code"].lower()
    assert client.get(f"/api/public/events/{lower}").status_code == 200


def test_invalid_event_code_is_404(client):
    assert client.get("/api/public/events/EVT-NOPE99").status_code == 404


def test_public_event_hides_photographer_details(client, event):
    body = client.get(f"/api/public/events/{event['event_code']}").json()
    assert "user_id" not in body and "id" not in body


def test_closed_event_blocks_guests(client, photographer, event):
    client.put(f"/api/events/{event['id']}", headers=photographer["headers"],
               json={"public_access": False})
    assert client.get(f"/api/public/events/{event['event_code']}").status_code == 403


def test_archived_event_blocks_guests(client, photographer, event):
    client.put(f"/api/events/{event['id']}", headers=photographer["headers"],
               json={"status": "ARCHIVED"})
    assert client.get(f"/api/public/events/{event['event_code']}").status_code == 403


# -- gallery ---------------------------------------------------------------
def test_gallery_lists_ready_photos_newest_first(client, photographer, event, upload):
    _seed_gallery(client, photographer, event, upload)
    body = client.get(f"/api/public/events/{event['event_code']}/photos").json()
    assert body["total"] == 3
    assert body["items"][0]["filename"] == "solo3.jpg"


def test_gallery_paginates(client, photographer, event, upload):
    upload(event["id"], photographer["headers"],
           [(f"p{i}.jpg", make_photo([1], size=(300 + i, 200))) for i in range(6)])
    body = client.get(f"/api/public/events/{event['event_code']}/photos?limit=2").json()
    assert len(body["items"]) == 2 and body["has_more"] is True


def test_gallery_photos_expose_urls_not_paths(client, photographer, event, upload):
    _seed_gallery(client, photographer, event, upload)
    item = client.get(f"/api/public/events/{event['event_code']}/photos").json()["items"][0]
    assert item["thumbnail_url"].startswith("/api/public/photos/")
    assert "storage" not in str(item) and "original_path" not in item


# -- selfie search ---------------------------------------------------------
def test_search_finds_only_photos_containing_the_guest(client, photographer, event, upload):
    _seed_gallery(client, photographer, event, upload)
    r = client.post(f"/api/public/events/{event['event_code']}/search",
                    files={"selfie": ("me.jpg", make_selfie(1), "image/jpeg")})
    assert r.status_code == 200
    body = r.json()
    assert body["match_count"] == 2
    names = {m["photo"]["filename"] for m in body["matches"]}
    assert names == {"solo1.jpg", "group12.jpg"}


def test_search_results_are_ordered_by_similarity(client, photographer, event, upload):
    _seed_gallery(client, photographer, event, upload)
    body = client.post(f"/api/public/events/{event['event_code']}/search",
                       files={"selfie": ("me.jpg", make_selfie(1), "image/jpeg")}).json()
    scores = [m["similarity"] for m in body["matches"]]
    assert scores == sorted(scores, reverse=True)


def test_search_returns_nothing_for_an_absent_guest(client, photographer, event, upload):
    _seed_gallery(client, photographer, event, upload)
    body = client.post(f"/api/public/events/{event['event_code']}/search",
                       files={"selfie": ("me.jpg", make_selfie(5), "image/jpeg")}).json()
    assert body["match_count"] == 0 and body["matches"] == []


def test_search_rejects_selfie_with_no_face(client, photographer, event, upload):
    _seed_gallery(client, photographer, event, upload)
    r = client.post(f"/api/public/events/{event['event_code']}/search",
                    files={"selfie": ("blank.jpg", make_empty_photo(), "image/jpeg")})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "NO_FACE"


def test_search_rejects_selfie_with_multiple_faces(client, photographer, event, upload):
    _seed_gallery(client, photographer, event, upload)
    r = client.post(f"/api/public/events/{event['event_code']}/search",
                    files={"selfie": ("two.jpg", make_photo([1, 2]), "image/jpeg")})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "MULTIPLE_FACES"


def test_search_rejects_a_non_image(client, event):
    r = client.post(f"/api/public/events/{event['event_code']}/search",
                    files={"selfie": ("x.jpg", make_corrupt_file(), "image/jpeg")})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "INVALID_IMAGE"


def test_search_never_crosses_event_boundaries(client, photographer, event, upload):
    """The critical isolation test: person 1 is in both events' photos."""
    _seed_gallery(client, photographer, event, upload)
    other = client.post("/api/events", headers=photographer["headers"],
                        json={"name": "Different Wedding"}).json()
    upload(other["id"], photographer["headers"],
           [("other1.jpg", make_photo([1], size=(500, 380)))])

    body = client.post(f"/api/public/events/{event['event_code']}/search",
                       files={"selfie": ("me.jpg", make_selfie(1), "image/jpeg")}).json()
    assert "other1.jpg" not in {m["photo"]["filename"] for m in body["matches"]}
    assert body["match_count"] == 2


def test_search_is_recorded_for_the_event(db, client, photographer, event, upload):
    from app.models import GuestSearch, PhotoMatch
    from sqlalchemy import select

    _seed_gallery(client, photographer, event, upload)
    client.post(f"/api/public/events/{event['event_code']}/search",
                files={"selfie": ("me.jpg", make_selfie(1), "image/jpeg")})
    searches = db.execute(select(GuestSearch)).scalars().all()
    assert len(searches) == 1 and searches[0].match_count == 2
    assert len(db.execute(select(PhotoMatch)).scalars().all()) == 2


def test_search_can_be_reopened_by_id(client, photographer, event, upload):
    _seed_gallery(client, photographer, event, upload)
    first = client.post(f"/api/public/events/{event['event_code']}/search",
                        files={"selfie": ("me.jpg", make_selfie(1), "image/jpeg")}).json()
    again = client.get(f"/api/public/searches/{first['search_id']}").json()
    assert again["match_count"] == first["match_count"]
    assert {m["photo"]["id"] for m in again["matches"]} == {m["photo"]["id"] for m in first["matches"]}


def test_unknown_search_id_is_404(client):
    assert client.get(f"/api/public/searches/{uuid.uuid4()}").status_code == 404


def test_search_on_closed_event_is_blocked(client, photographer, event, upload):
    _seed_gallery(client, photographer, event, upload)
    client.put(f"/api/events/{event['id']}", headers=photographer["headers"],
               json={"public_access": False})
    r = client.post(f"/api/public/events/{event['event_code']}/search",
                    files={"selfie": ("me.jpg", make_selfie(1), "image/jpeg")})
    assert r.status_code == 403


def test_search_is_rate_limited(client, event, monkeypatch):
    from app.services.rate_limit import search_limiter

    monkeypatch.setattr(search_limiter, "limit", 3)
    search_limiter.reset()
    codes = [
        client.post(f"/api/public/events/{event['event_code']}/search",
                    files={"selfie": ("me.jpg", make_selfie(1), "image/jpeg")}).status_code
        for _ in range(5)
    ]
    assert 429 in codes


# -- delivery --------------------------------------------------------------
def test_guest_can_load_thumbnail_and_original(client, photographer, event, upload):
    _seed_gallery(client, photographer, event, upload)
    item = client.get(f"/api/public/events/{event['event_code']}/photos").json()["items"][0]
    thumb = client.get(item["thumbnail_url"])
    original = client.get(item["original_url"])
    assert thumb.status_code == 200 and thumb.headers["content-type"] == "image/webp"
    assert original.status_code == 200
    # The gallery must not be shipping full-resolution files.
    assert len(thumb.content) < len(original.content)


def test_download_sets_attachment_filename(client, photographer, event, upload):
    _seed_gallery(client, photographer, event, upload)
    item = client.get(f"/api/public/events/{event['event_code']}/photos").json()["items"][0]
    r = client.get(item["original_url"] + "?download=true")
    assert "attachment" in r.headers["content-disposition"]


def test_photo_delivery_blocked_once_event_is_closed(client, photographer, event, upload):
    _seed_gallery(client, photographer, event, upload)
    item = client.get(f"/api/public/events/{event['event_code']}/photos").json()["items"][0]
    client.put(f"/api/events/{event['id']}", headers=photographer["headers"],
               json={"public_access": False})
    assert client.get(item["thumbnail_url"]).status_code == 404


def test_unknown_photo_delivery_is_404(client):
    assert client.get(f"/api/public/photos/{uuid.uuid4()}/thumbnail").status_code == 404
