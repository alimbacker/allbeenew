# ALLBEE Instant

**Capture. Match. Deliver. — On the Spot.**

Event photography delivered while the event is still happening. The
photographer uploads as they shoot; guests scan a QR code, take one selfie, and
get every photo they appear in — no app, no account, no waiting.

Everything runs on your own infrastructure. Photos sit on your server's
filesystem, PostgreSQL runs next to it, and face recognition runs locally on
the CPU. **No AWS, and no paid cloud face-recognition service anywhere.**

---

## What's in the box

| Part | Stack | Purpose |
|---|---|---|
| `backend/` | Python, FastAPI, SQLAlchemy, Alembic, PostgreSQL + pgvector | API, storage, face recognition |
| `frontend/` | Next.js 14, React 18, TypeScript, Tailwind | Photographer dashboard and guest pages |
| `desktop-uploader/` | Python, PySide6 | Windows app that watches a folder and uploads automatically |

---

## Quick start

You need **Python 3.11+**, **Node 18+**, and **Docker** (for PostgreSQL only).

### 1. Start PostgreSQL

```bash
docker compose up -d
```

This runs `pgvector/pgvector:pg16`, which already includes the vector
extension. Nothing else is containerised — the app runs on the host so photos
land on a real filesystem you control.

> **No Docker?** Install PostgreSQL 14+ and the
> [pgvector](https://github.com/pgvector/pgvector) extension yourself, create a
> database, then point `DATABASE_URL` at it. The app also runs on SQLite with
> no extension at all — see [Running without PostgreSQL](#running-without-postgresql).

### 2. Backend

**Windows (PowerShell or cmd):**

```bat
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m app.face.download
alembic upgrade head
uvicorn app.main:app --reload
```

**Linux / macOS:**

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.face.download
alembic upgrade head
uvicorn app.main:app --reload
```

The API is now on <http://localhost:8000>, with interactive docs at
<http://localhost:8000/docs>.

`python -m app.face.download` fetches ~190 MB of face-recognition models once.
Check they loaded:

```bash
curl http://localhost:8000/health
```

`"face_engine": {"loaded": true}` means you're ready.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>.

### 4. Demo data (optional)

```bash
cd backend
python -m scripts.seed
```

Creates:

```
Photographer   demo@allbee.local / Demo@12345
Event          ALLBEE Demo Wedding  (EVT-DEMO01)
```

Add real photos at the same time with `python -m scripts.seed --photos "C:\Wedding\Photos"`.
They go through the exact same upload path as the API, so they get thumbnails
and face detection normally.

### 5. Desktop uploader (optional)

```bash
cd desktop-uploader
pip install -r requirements.txt
python main.py
```

---

## Try the whole flow

1. Register at <http://localhost:3000/register>.
2. Create an event. You get a code like `EVT-8F42K9` automatically.
3. Open **QR code** and scan it with your phone (or just open the guest link).
4. Go to **Upload** and add photos with people in them.
5. Watch the counters: photos move from `PROCESSING` to `READY` as faces are found.
6. On the guest page, tap **Find my photos** and take a selfie.
7. Your photos come back, ordered by how confident the match is. Tap one to
   view, download or share it.

The guest gallery updates on its own while you keep uploading — leave it open
on a second device and watch photos appear.

---

## Configuration

Everything lives in `backend/.env` (copy from `.env.example`). The settings
that matter most:

| Setting | Default | What it does |
|---|---|---|
| `DATABASE_URL` | `postgresql://allbee:allbee@localhost:5432/allbee` | Database connection |
| `STORAGE_PATH` | `./storage` | Where photo files are written |
| `JWT_SECRET` | `change-this-secret` | **Change this before deploying** |
| `PUBLIC_BASE_URL` | `http://localhost:3000` | What QR codes point at — must be reachable from a guest's phone |
| `FACE_MATCH_THRESHOLD` | `0.38` | How similar a face must be to count as a match |
| `MAX_UPLOAD_SIZE_MB` | `25` | Per-file upload limit |
| `WORKER_CONCURRENCY` | `2` | Face-processing threads — roughly one per two cores |

Generate a real secret with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

> **`PUBLIC_BASE_URL` catches people out.** QR codes encode
> `PUBLIC_BASE_URL/event/{code}`. If it says `localhost`, the QR code will only
> work on the machine running the server. Set it to your LAN IP for testing on
> a phone (`http://192.168.1.20:3000`) or your real domain in production.

Tuning the match threshold is covered in **[docs/FACE_RECOGNITION.md](docs/FACE_RECOGNITION.md)**.

---

## Storage layout

```
storage/
└── events/
    └── EVT-8F42K9/
        ├── originals/     full-resolution files, untouched
        ├── thumbnails/    WEBP, max 640px — what the gallery loads
        └── selfies/       guest search selfies
```

The database stores only *relative* paths, so moving storage to another disk or
another server is a change to `STORAGE_PATH` and a file copy — no data
migration and no code changes.

**These files are never served directly by the web server.** Every byte goes
through `/api/public/photos/{id}/thumbnail` or `/original`, which check that the
photo exists, that its event is open to guests, and that the resolved path is
still inside the storage root.

---

## Running without PostgreSQL

Useful on a laptop before you've set anything up:

```bash
DATABASE_URL=sqlite:///./allbee.db uvicorn app.main:app --reload
```

Face search then runs as an exact brute-force scan in NumPy instead of an
indexed pgvector query. Results are identical; it's linear in the number of
faces, so use PostgreSQL for real events.

---

## Tests

```bash
cd backend
pytest
```

99 tests covering authentication, event ownership, uploads, duplicate
detection, path-traversal defences, the guest journey and cross-event
isolation. They run on SQLite with a deterministic stand-in for the face
engine, so they need no database server and no model files.

To also exercise the **real** face models against real photographs:

```bash
python -m app.face.download
pytest tests/test_face_engine.py
```

These are skipped automatically when the models aren't present.

---

## Documentation

| Document | Contents |
|---|---|
| [docs/FACE_RECOGNITION.md](docs/FACE_RECOGNITION.md) | How matching works, threshold tuning, measured accuracy |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Self-hosting on Linux with Nginx, HTTPS and systemd |
| [docs/BACKUP.md](docs/BACKUP.md) | Backing up the database and photo storage |
| [docs/PRIVACY.md](docs/PRIVACY.md) | What guest data is held, and retention |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How the pieces fit, and where to extend |
| <http://localhost:8000/docs> | Interactive API reference |

---

## API summary

Full schemas, validation rules and error responses are at `/docs`.

```
POST   /api/auth/register              Create an account
POST   /api/auth/login                 Get a JWT
GET    /api/auth/me                    Current photographer

POST   /api/events                     Create an event
GET    /api/events                     List your events
GET    /api/events/dashboard           Totals and recent events
GET    /api/events/{id}                Event detail with live counters
PUT    /api/events/{id}                Update an event
DELETE /api/events/{id}                Delete an event and its photos
GET    /api/events/{id}/qr             QR code as PNG

POST   /api/events/{id}/photos         Upload photos
GET    /api/events/{id}/photos         List photos (paginated)
DELETE /api/photos/{id}                Delete a photo
GET    /api/photos/{id}/original       Download (photographer)

GET    /api/public/events/{code}                 Event detail for guests
GET    /api/public/events/{code}/photos          Live gallery
GET    /api/public/events/{code}/stream          Server-Sent Events feed
POST   /api/public/events/{code}/search          Selfie search
GET    /api/public/searches/{id}                 Re-open past results
GET    /api/public/photos/{id}/thumbnail         Gallery thumbnail
GET    /api/public/photos/{id}/original          Full-resolution photo
```

Guest endpoints need no token — the event code is the key.

---

## Troubleshooting

**`face_engine.loaded` is false.**
Run `python -m app.face.download`. Photos still upload and store while the
engine is missing; they queue as `PROCESSING`. Once models are in place, use
**Settings → Retry failed photos** on the event, or
`POST /api/events/{id}/photos/reprocess`.

**The QR code doesn't work on my phone.**
`PUBLIC_BASE_URL` is probably still `localhost`. See
[Configuration](#configuration).

**Guests get few or no matches.**
Lower `FACE_MATCH_THRESHOLD` (try `0.32`) and restart. See
[docs/FACE_RECOGNITION.md](docs/FACE_RECOGNITION.md).

**Uploads fail with 413.**
Raise `MAX_UPLOAD_SIZE_MB`. Behind Nginx, also raise `client_max_body_size`.

**`alembic upgrade head` fails on `CREATE EXTENSION vector`.**
Your PostgreSQL doesn't have pgvector, or the user isn't a superuser. Use the
`pgvector/pgvector:pg16` image from `docker-compose.yml`, or install the
extension as a superuser first.

**Face processing is slow.**
It's CPU-bound. Raise `WORKER_CONCURRENCY` toward your core count, or switch to
the lighter engine with `FACE_ENGINE=opencv` and
`python -m app.face.download --engine opencv`.
