# Architecture

## Shape

```
Photographer                                  Guest (phone, no account)
     |                                                  |
     |  JWT                                             |  event code
     v                                                  v
+------------------ Next.js (App Router) ------------------+
|  /dashboard/*  dark UI, working tool                     |
|  /event/*      light UI, mobile-first, one-shot use      |
+----------------------------+-----------------------------+
                             | /api/*
                             v
+--------------------------- FastAPI ----------------------+
|  routes/    auth, events, photos, public                 |
|  deps.py    authentication and ownership, once           |
|  services/  storage, images, photos, search, live, tasks |
|  face/      engine interface + ArcFace / OpenCV backends |
+------------+------------------------------+--------------+
             |                              |
             v                              v
   PostgreSQL + pgvector          storage/events/{code}/
   metadata + face vectors        originals, thumbnails, selfies
```

Two surfaces, chosen for their real conditions: the dashboard is dark because
photographers work in dim halls for hours and photos need to read true against
it; guest pages are light because guests are outdoors in daylight.

## Request paths

**Upload** (fast, synchronous):

```
validate bytes -> SHA-256 -> reject duplicate -> write original ->
write thumbnail -> insert row (PROCESSING) -> queue job -> respond
```

**Worker** (background thread):

```
read original -> downscale -> detect faces -> embed each ->
insert faces -> mark READY -> publish to the live feed
```

The request never waits on face detection. A photographer pushing 500 photos is
not blocked behind the model.

**Guest search:**

```
validate selfie -> require exactly one face -> embed ->
vector search WHERE event_id = this event -> best score per photo ->
filter by threshold -> persist search + matches -> return
```

## Decisions worth knowing

**Face models run through onnxruntime, not the `insightface` package.**
`insightface`, `dlib` and `face_recognition` need a C toolchain; on Windows
that means Visual Studio Build Tools. `onnxruntime` and `opencv-python` are
plain wheels. Same models, no compiler. See
[FACE_RECOGNITION.md](FACE_RECOGNITION.md).

**`faces.event_id` is denormalised from `photos`.**
Every guest search filters by event. Carrying the event on the face row keeps
that filter out of a join and inside the indexed scan.

**Embeddings use a dialect-aware column type.**
`Vector(dim)` on PostgreSQL, a JSON array everywhere else. The search service
picks its strategy from the dialect: an indexed pgvector query, or an exact
NumPy scan. Same results either way, which is what lets the test suite and a
laptop run with no database server.

**Storage paths in the database are relative.**
`events/EVT-XXXXXX/originals/abc.jpg`, never `/var/lib/...`. Moving storage to
another disk or another server is a config change and a file copy.

**Every file goes through the API.**
`storage/` is never mapped by the web server. Delivery endpoints check the
photo exists, the event is open to guests, and the resolved path is still
inside the storage root — the last one being the actual defence against a
crafted path.

**Ownership lives in `deps.py`.**
`owned_event` and `owned_photo` put ownership in the query rather than in an
`if` afterwards, so a new endpoint gets the check by declaring the dependency.
They return 404 rather than 403, so the API never confirms that someone else's
event exists.

**Uploads are one request per file.**
More round trips, but real per-file progress, a failure that costs one frame
instead of a batch, and retries that do not re-send hundreds of megabytes.

## Extension points

Each of these is isolated behind one module, so adding it does not ripple.

| Want | Change | Leave alone |
|---|---|---|
| Celery / RQ / arq | `services/tasks.py` — implement `submit` against a broker | Everything that calls `task_queue.submit` |
| S3-compatible or NFS storage | `services/storage.py` — same five methods | Routes, models, workers |
| A different face model | `face/` — implement the `FaceEngine` protocol, register in `engine.py` | Search, ingestion, API |
| Redis pub/sub for the live feed | `services/live.py` — same `publish`/`subscribe` contract | The hook, the routes |
| Redis rate limiting | `services/rate_limit.py` | The routes calling `enforce` |

## Known limits

**The live feed and the task queue are per-process.** Running multiple uvicorn
workers gives each its own queue and its own Server-Sent Events subscribers,
which still works — every client gets updates for photos handled by its own
worker, and the polling fallback covers the rest — but for a clean multi-worker
setup, move `services/live.py` to Redis pub/sub and `services/tasks.py` to a
real broker.

**Rate limiting is in-memory**, so limits are per process. Fine for one or two
workers; use Redis beyond that.

**Face detection is CPU-bound.** Throughput scales with `WORKER_CONCURRENCY`
and cores. Each uvicorn worker loads its own copy of the models, so budget
roughly 1 GB per worker.

## Deliberately not built

The spec lists these as future work, and none is needed for the MVP:
WhatsApp/SMS/email delivery, guest QR cards, teams and multiple photographers,
white-label galleries, custom domains, payments, watermarks, AI photo
selection, analytics, favourites, bulk and ZIP downloads, face clustering.

The structure above is what makes them additive rather than invasive — for
example, bulk ZIP download is a new route over the existing storage service,
and delivery channels hang off the existing match records.
