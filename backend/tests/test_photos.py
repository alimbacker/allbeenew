"""Upload, validation, duplicate protection, storage layout and deletion."""

from __future__ import annotations

import uuid

from conftest import make_corrupt_file, make_empty_photo, make_photo


def test_upload_stores_photo_and_generates_thumbnail(client, photographer, event, upload, storage_root):
    body = upload(event["id"], photographer["headers"], [("IMG_0001.JPG", make_photo([1]))])
    assert body["uploaded"] == 1
    photo = body["results"][0]["photo"]
    assert photo["filename"] == "IMG_0001.JPG"

    code = event["event_code"]
    originals = list((storage_root / "events" / code / "originals").glob("*"))
    thumbs = list((storage_root / "events" / code / "thumbnails").glob("*.webp"))
    assert len(originals) == 1 and len(thumbs) == 1
    # Thumbnails must actually be smaller than the original.
    assert thumbs[0].stat().st_size < originals[0].stat().st_size


def test_photo_reaches_ready_after_processing(client, photographer, event, upload):
    body = upload(event["id"], photographer["headers"], [("a.jpg", make_photo([1, 2]))])
    photo_id = body["results"][0]["photo"]["id"]
    r = client.get(f"/api/photos/{photo_id}", headers=photographer["headers"])
    assert r.json()["status"] == "READY"
    assert r.json()["face_count"] == 2


def test_faces_are_recorded_per_photo(db, client, photographer, event, upload):
    from app.models import Face
    from sqlalchemy import select

    upload(event["id"], photographer["headers"], [("group.jpg", make_photo([1, 2, 3]))])
    faces = db.execute(select(Face)).scalars().all()
    assert len(faces) == 3
    assert all(f.bounding_box["width"] > 0 for f in faces)
    assert all(str(f.event_id) == event["id"] for f in faces)


def test_photo_with_no_faces_still_becomes_ready(client, photographer, event, upload):
    body = upload(event["id"], photographer["headers"], [("empty.jpg", make_empty_photo())])
    photo = body["results"][0]["photo"]
    r = client.get(f"/api/photos/{photo['id']}", headers=photographer["headers"])
    assert r.json()["status"] == "READY"
    assert r.json()["face_count"] == 0


def test_multiple_files_in_one_request(client, photographer, event, upload):
    files = [(f"IMG_{i:04d}.jpg", make_photo([1], size=(200 + i, 200))) for i in range(5)]
    body = upload(event["id"], photographer["headers"], files)
    assert body["uploaded"] == 5


def test_duplicate_upload_is_detected(client, photographer, event, upload):
    data = make_photo([1])
    upload(event["id"], photographer["headers"], [("first.jpg", data)])
    body = upload(event["id"], photographer["headers"], [("again.jpg", data)])
    assert body["duplicates"] == 1 and body["uploaded"] == 0
    assert body["results"][0]["status"] == "duplicate"


def test_same_file_allowed_in_a_different_event(client, photographer, event, upload):
    data = make_photo([1])
    upload(event["id"], photographer["headers"], [("x.jpg", data)])
    other = client.post("/api/events", headers=photographer["headers"],
                        json={"name": "Second Event"}).json()
    body = upload(other["id"], photographer["headers"], [("x.jpg", data)])
    assert body["uploaded"] == 1


def test_corrupt_file_is_rejected(client, photographer, event, upload):
    body = upload(event["id"], photographer["headers"], [("evil.jpg", make_corrupt_file())])
    assert body["rejected"] == 1
    assert body["results"][0]["status"] == "rejected"


def test_disallowed_file_type_is_rejected(client, photographer, event, upload):
    """A GIF is a real image but is not in ALLOWED_EXTENSIONS."""
    import io
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (10, 10, 10)).save(buf, format="GIF")
    body = upload(event["id"], photographer["headers"], [("anim.gif", buf.getvalue())])
    assert body["rejected"] == 1


def test_oversized_file_is_rejected(client, photographer, event, upload):
    from app.config import settings

    oversized = b"\xff\xd8\xff" + b"\x00" * (settings.max_upload_bytes + 1024)
    body = upload(event["id"], photographer["headers"], [("huge.jpg", oversized)])
    assert body["rejected"] == 1


def test_mixed_batch_reports_each_file_independently(client, photographer, event, upload):
    dupe = make_photo([2])
    upload(event["id"], photographer["headers"], [("d.jpg", dupe)])
    body = upload(event["id"], photographer["headers"], [
        ("good.jpg", make_photo([1])),
        ("d.jpg", dupe),
        ("bad.jpg", make_corrupt_file()),
    ])
    assert (body["uploaded"], body["duplicates"], body["rejected"]) == (1, 1, 1)


def test_filename_with_path_traversal_is_sanitised(client, photographer, event, upload, storage_root):
    body = upload(event["id"], photographer["headers"],
                  [("../../../../etc/passwd.jpg", make_photo([1]))])
    assert body["uploaded"] == 1
    assert "/" not in body["results"][0]["photo"]["filename"]
    assert not (storage_root.parent / "passwd.jpg").exists()


def test_windows_style_path_is_reduced_to_basename(client, photographer, event, upload):
    body = upload(event["id"], photographer["headers"],
                  [("D:\\Wedding\\Photos\\IMG_9.jpg", make_photo([3]))])
    assert body["results"][0]["photo"]["filename"] == "IMG_9.jpg"


def test_upload_requires_ownership(client, event, second_photographer, upload):
    r = client.post(f"/api/events/{event['id']}/photos",
                    headers=second_photographer["headers"],
                    files=[("files", ("x.jpg", make_photo([1]), "image/jpeg"))])
    assert r.status_code == 404


def test_upload_requires_auth(client, event):
    r = client.post(f"/api/events/{event['id']}/photos",
                    files=[("files", ("x.jpg", make_photo([1]), "image/jpeg"))])
    assert r.status_code == 401


def test_list_photos_paginates(client, photographer, event, upload):
    upload(event["id"], photographer["headers"],
           [(f"p{i}.jpg", make_photo([1], size=(300 + i, 200))) for i in range(7)])
    r = client.get(f"/api/events/{event['id']}/photos?limit=3&offset=0",
                   headers=photographer["headers"])
    body = r.json()
    assert len(body["items"]) == 3 and body["total"] == 7 and body["has_more"] is True


def test_delete_photo_removes_row_and_files(client, photographer, event, upload, storage_root):
    body = upload(event["id"], photographer["headers"], [("gone.jpg", make_photo([1]))])
    photo_id = body["results"][0]["photo"]["id"]
    assert client.delete(f"/api/photos/{photo_id}", headers=photographer["headers"]).status_code == 200
    assert client.get(f"/api/photos/{photo_id}", headers=photographer["headers"]).status_code == 404
    code = event["event_code"]
    assert list((storage_root / "events" / code / "originals").glob("*")) == []


def test_deleting_photo_cascades_to_faces(db, client, photographer, event, upload):
    from app.models import Face
    from sqlalchemy import select

    body = upload(event["id"], photographer["headers"], [("g.jpg", make_photo([1, 2]))])
    photo_id = body["results"][0]["photo"]["id"]
    assert len(db.execute(select(Face)).scalars().all()) == 2
    client.delete(f"/api/photos/{photo_id}", headers=photographer["headers"])
    db.expire_all()
    assert db.execute(select(Face)).scalars().all() == []


def test_delete_photo_requires_ownership(client, photographer, event, upload, second_photographer):
    body = upload(event["id"], photographer["headers"], [("p.jpg", make_photo([1]))])
    photo_id = body["results"][0]["photo"]["id"]
    r = client.delete(f"/api/photos/{photo_id}", headers=second_photographer["headers"])
    assert r.status_code == 404


def test_deleting_event_removes_its_storage_directory(client, photographer, event, upload, storage_root):
    upload(event["id"], photographer["headers"], [("p.jpg", make_photo([1]))])
    client.delete(f"/api/events/{event['id']}", headers=photographer["headers"])
    assert not (storage_root / "events" / event["event_code"]).exists()


def test_photographer_can_download_own_original(client, photographer, event, upload):
    body = upload(event["id"], photographer["headers"], [("orig.jpg", make_photo([1]))])
    photo_id = body["results"][0]["photo"]["id"]
    r = client.get(f"/api/photos/{photo_id}/original", headers=photographer["headers"])
    assert r.status_code == 200 and len(r.content) > 0


def test_photographer_cannot_download_another_photographers_original(
    client, photographer, event, upload, second_photographer
):
    body = upload(event["id"], photographer["headers"], [("orig.jpg", make_photo([1]))])
    photo_id = body["results"][0]["photo"]["id"]
    r = client.get(f"/api/photos/{photo_id}/original", headers=second_photographer["headers"])
    assert r.status_code == 404


def test_unknown_photo_id_is_404(client, photographer):
    r = client.get(f"/api/photos/{uuid.uuid4()}", headers=photographer["headers"])
    assert r.status_code == 404
