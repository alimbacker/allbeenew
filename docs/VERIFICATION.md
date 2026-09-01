# Verification record

What was actually run, and what was not. Reproduce any of it yourself with the
commands given.

## Summary

| Area | Method | Result |
|---|---|---|
| Backend unit tests | SQLite + deterministic face engine | **99 passed** |
| Face models | Real ONNX models, real photographs | **7 passed** |
| Full product flow | Live HTTP server, SQLite, real models | **all checks passed** |
| Full product flow | Live HTTP server, **PostgreSQL 16 + pgvector 0.6.0**, real models | **all checks passed** |
| Alembic migration | SQLite and PostgreSQL | applies cleanly on both |
| Frontend | `tsc --noEmit` and `next build` | 18 routes, no errors |
| Desktop uploader | Qt window construction + logic tests | window builds, 6 logic checks pass |
| OpenAPI | Schema generation | 20 endpoints, none missing a summary |

## Face matching accuracy

Measured with real photographs bundled inside installed Python packages, so
these are reproducible offline. The "selfie" is deliberately degraded to
resemble a phone photo: scaled to 240px, brightened, tilted 8°, JPEG quality 40.

| Comparison | Cosine similarity |
|---|---|
| Degraded selfie vs. same person's solo portrait | **0.738** |
| Degraded selfie vs. same person inside a group photo | **0.735** |
| Degraded selfie vs. a different person | **≈0.00** |
| Photo containing no people | no faces detected |

The gap between a correct and an incorrect match is roughly 0.74 versus 0.00.
That is what makes `FACE_MATCH_THRESHOLD=0.38` a safe default with room for
poor event conditions. See [FACE_RECOGNITION.md](FACE_RECOGNITION.md).

```bash
cd backend
python -m app.face.download
pytest tests/test_face_engine.py -v
```

## The full spec flow

Every step of the flow the spec calls the most important requirement was
executed against a running `uvicorn` process over real HTTP — no mocks, no
stubs, no fixtures:

```
register -> login -> create event -> generate QR -> decode QR and open it as a
guest -> upload real photos -> files on disk -> thumbnails -> background face
processing -> live gallery -> guest selfie -> vector search -> matched photos
-> download
```

Checks that passed, in both the SQLite and PostgreSQL runs:

- QR PNG decodes to the guest URL for that event code
- Guest opens the event with no token
- 4 photos uploaded; re-uploading one is reported as a duplicate, not an error
- Originals and thumbnails written to `storage/events/{code}/`, thumbnails smaller
- All photos reach `READY`, 0 failed, 4 faces indexed
- Gallery lists ready photos newest first, and leaks no filesystem paths
- Selfie search returns exactly the 2 photos containing that guest
- It does **not** return the other person's photo or the photo with nobody in it
- Results ordered by similarity
- A selfie with no face returns `NO_FACE`; one with two faces returns `MULTIPLE_FACES`
- Download bytes are byte-identical to the original on disk
- The same person's photo in a **different event** is not returned
- Closing the guest link immediately blocks both the event page and photo delivery

## PostgreSQL and pgvector

The production search path was run against a real PostgreSQL 16 server with
pgvector 0.6.0, not only the fallback.

Confirmed directly in the database:

```
faces.embedding  ->  udt_name = vector
ix_faces_embedding_hnsw  ->  USING hnsw (embedding vector_cosine_ops)
                             WITH (m='16', ef_construction='64')
```

The search service logs a warning and falls back to NumPy if the pgvector query
fails. During the PostgreSQL run that warning appeared **zero times**, so the
indexed `DISTINCT ON ... <=>` cosine query is what actually executed.

The similarity scores from the PostgreSQL run and the SQLite/NumPy run were
identical to four decimal places (0.7382 and 0.7352 in both), which
cross-validates the two implementations against each other.

## Security checks covered by tests

- Passwords stored as bcrypt hashes, salted (two hashes of the same password differ)
- Wrong password and unknown email return the same message, so accounts cannot be enumerated
- Expired and tampered JWTs rejected
- One photographer cannot read, update, delete or download another's events or photos — 404, not 403, so the API never confirms the resource exists
- Path traversal blocked at three layers: filename sanitising, relative-path validation, and a final storage-root bounds check
- `../../etc/passwd`, `..\\..\\windows\\system32`, and absolute paths all rejected
- Uploaded filenames reduced to a safe basename; Windows paths handled
- Guest search rate limited
- Closed or archived events block the gallery, search and file delivery

## Not verified

Stated plainly so nothing is assumed:

- **No browser testing.** The frontend compiles and typechecks, and every API
  it calls is tested, but no page was opened in a real browser. Layout,
  responsiveness and the camera capture flow are unexercised.
- **The desktop uploader was not run against a live server.** Its window
  constructs, and the dedupe ledger and folder-scanning rules are unit-tested,
  but no end-to-end upload from a watched folder was performed.
- **Server-Sent Events were not exercised over a live connection.** The
  endpoint and the bus are implemented and the client has a polling fallback,
  but no browser held the stream open.
- **No load testing.** The 5,000-photo target is addressed by design —
  pagination, thumbnails, indexes, HNSW, background processing — but was not
  measured.
- **Multi-worker deployment.** The live feed and task queue are per-process.
  See the known limits in [ARCHITECTURE.md](ARCHITECTURE.md).

## Reproducing

```bash
# Unit tests: no database server, no model download
cd backend && pytest

# Real face models
python -m app.face.download && pytest tests/test_face_engine.py -v

# Against PostgreSQL
docker compose up -d
DATABASE_URL=postgresql://allbee:allbee@localhost:5432/allbee alembic upgrade head

# Frontend
cd frontend && npm ci && npx tsc --noEmit && npm run build
```
