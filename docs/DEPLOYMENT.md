# Self-hosted deployment

Target: one Linux server (Ubuntu 22.04+ or Debian 12) running everything.
No AWS, no managed services.

```
Internet
   |
Domain (A record)
   |
Nginx  --  TLS, static files, reverse proxy
   |
   +--> Next.js   :3000   guest + dashboard UI
   +--> FastAPI   :8000   API, face processing, file delivery
                     |
                     +--> PostgreSQL + pgvector  :5432
                     +--> /var/lib/allbee/storage
```

A 4-core / 8 GB VPS comfortably handles an event of several thousand photos.
Face detection is the CPU-bound part; storage is the thing that grows.

## 1. System packages

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip nginx postgresql postgresql-contrib \
                    postgresql-16-pgvector git curl
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

## 2. Database

```bash
sudo -u postgres psql <<'SQL'
CREATE USER allbee WITH PASSWORD 'use-a-real-password';
CREATE DATABASE allbee OWNER allbee;
\c allbee
CREATE EXTENSION IF NOT EXISTS vector;
SQL
```

The extension must be created by a superuser, which is why it happens here
rather than in the migration.

## 3. Application user and directories

Photos are stored outside the code directory so a redeploy can never touch
them.

```bash
sudo useradd --system --create-home --home-dir /opt/allbee allbee
sudo mkdir -p /var/lib/allbee/storage /var/lib/allbee/models
sudo chown -R allbee:allbee /var/lib/allbee

sudo -u allbee git clone <your-repo> /opt/allbee/app
```

## 4. Backend

```bash
sudo -u allbee -H bash <<'EOF_INNER'
cd /opt/allbee/app/backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env
EOF_INNER
```

Edit `/opt/allbee/app/backend/.env`:

```ini
ENVIRONMENT=production
DEBUG=false

DATABASE_URL=postgresql://allbee:use-a-real-password@localhost:5432/allbee
JWT_SECRET=<paste output of: python3 -c "import secrets; print(secrets.token_urlsafe(48))">

STORAGE_PATH=/var/lib/allbee/storage
FACE_MODEL_DIR=/var/lib/allbee/models

# Must be the public URL a guest's phone can reach — this is what QR codes encode.
PUBLIC_BASE_URL=https://photos.example.com
CORS_ORIGINS=https://photos.example.com

WORKER_CONCURRENCY=4
MAX_UPLOAD_SIZE_MB=25
```

Then fetch models and run migrations:

```bash
cd /opt/allbee/app/backend
sudo -u allbee ./venv/bin/python -m app.face.download
sudo -u allbee ./venv/bin/alembic upgrade head
```

## 5. Frontend

```bash
cd /opt/allbee/app/frontend
sudo -u allbee npm ci
sudo -u allbee npm run build
```

Fonts are bundled from npm rather than fetched from Google, so this build works
on a server with no outbound internet access.

## 6. systemd services

`/etc/systemd/system/allbee-api.service`:

```ini
[Unit]
Description=ALLBEE Instant API
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=allbee
Group=allbee
WorkingDirectory=/opt/allbee/app/backend
Environment="PATH=/opt/allbee/app/backend/venv/bin"
ExecStart=/opt/allbee/app/backend/venv/bin/uvicorn app.main:app \
          --host 127.0.0.1 --port 8000 --workers 2 --proxy-headers
Restart=always
RestartSec=5

# Face models load into memory per worker; give it room.
MemoryMax=4G
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ReadWritePaths=/var/lib/allbee

[Install]
WantedBy=multi-user.target
```

> Each uvicorn worker loads its own copy of the models and keeps its own
> background queue and Server-Sent Events subscribers. Two workers is a
> reasonable default. Going wider means moving the live feed to Redis pub/sub —
> see [ARCHITECTURE.md](ARCHITECTURE.md).

`/etc/systemd/system/allbee-web.service`:

```ini
[Unit]
Description=ALLBEE Instant frontend
After=network.target

[Service]
Type=simple
User=allbee
Group=allbee
WorkingDirectory=/opt/allbee/app/frontend
Environment="NODE_ENV=production"
Environment="NEXT_PUBLIC_API_URL=http://127.0.0.1:8000"
ExecStart=/usr/bin/npm run start
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now allbee-api allbee-web
sudo systemctl status allbee-api
```

## 7. Nginx

`/etc/nginx/sites-available/allbee`:

```nginx
server {
    listen 80;
    server_name photos.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name photos.example.com;

    ssl_certificate     /etc/letsencrypt/live/photos.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/photos.example.com/privkey.pem;

    # Photographers upload large files from venue wifi.
    client_max_body_size 30m;
    client_body_timeout  300s;

    # The storage directory is NEVER exposed here. Every photo is served by
    # the API, which checks ownership and event visibility first.
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout 300s;
        proxy_send_timeout 300s;

        # Let the API stream files and Server-Sent Events straight through.
        proxy_buffering off;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host              $host;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade    $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/allbee /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

> `proxy_buffering off` matters. With buffering on, Nginx holds the
> Server-Sent Events stream and the live gallery stops updating. The API also
> sends `X-Accel-Buffering: no` as a second line of defence.

## 8. HTTPS

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d photos.example.com
```

HTTPS is not optional here: **the browser camera API only works on a secure
origin**, so without it guests cannot take a selfie in-page.

## 9. Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

PostgreSQL stays on localhost. Do not expose 5432.

## 10. Verify

```bash
curl https://photos.example.com/health
```

Expect `"status":"ok"` and `"face_engine":{"loaded":true}`.

Then walk the real flow: register, create an event, upload a few photos,
open the QR code on a phone, and run a selfie search.

## Updating

```bash
cd /opt/allbee/app
sudo -u allbee git pull
sudo -u allbee ./backend/venv/bin/pip install -r backend/requirements.txt
sudo -u allbee ./backend/venv/bin/alembic -c backend/alembic.ini upgrade head
sudo -u allbee npm --prefix frontend ci
sudo -u allbee npm --prefix frontend run build
sudo systemctl restart allbee-api allbee-web
```

Photos are untouched by any of this — they live in `/var/lib/allbee/storage`.

## Moving to a different server

The architecture is designed for this. The database stores only relative
paths, so:

1. `pg_dump` the database, restore it on the new host.
2. `rsync` `/var/lib/allbee/storage` across.
3. Set `STORAGE_PATH` on the new host.
4. Point DNS at it.

No code changes and no data migration.


---

# Option B: frontend on Vercel, backend on your own server

Vercel cannot host the backend. That is not a configuration problem:

- **Photos need a real filesystem.** Vercel's is ephemeral, so
  `storage/events/...` would not survive between requests.
- **Face processing runs on background threads** that outlive the HTTP
  response. Serverless functions are stopped as soon as they reply.
- **The models are ~190 MB** held in memory. Serverless cannot keep that warm.
- **Request bodies are capped at 4.5 MB**, well under the 25 MB upload limit.

The frontend, though, is a good fit for Vercel. The backend goes on any host
with a persistent disk -- a VPS as in Option A, or Render / Railway / Fly.io
with a volume attached.

## 1. Deploy the backend first

Follow Option A above, but skip the Next.js and `allbee-web` parts. You want
the API reachable at its own HTTPS hostname, for example
`https://api.yourdomain.com`.

Set these in `backend/.env`, using the **frontend's** URL for both:

```ini
PUBLIC_BASE_URL=https://allbeenew.vercel.app
CORS_ORIGINS=https://allbeenew.vercel.app
```

`PUBLIC_BASE_URL` is what QR codes encode, so it has to be the page a guest's
phone should land on. `CORS_ORIGINS` is what the browser is permitted to call
the API from; it must match exactly, scheme included.

Check it from your laptop before going further:

```bash
curl https://api.yourdomain.com/health
```

## 2. Point the frontend at it

In Vercel: **Project → Settings → Environment Variables**

```
NEXT_PUBLIC_API_URL = https://api.yourdomain.com
```

Add it to Production, Preview and Development, then **redeploy**. Environment
variables are baked in at build time, so an existing deployment will not pick
this up until it is rebuilt.

With this set, the browser calls your backend directly instead of routing
through Vercel. That is deliberate: proxying uploads through Vercel would
subject every photo to its 4.5 MB request-body limit.

## 3. Vercel project settings

Because the repository has `backend/` and `frontend/` side by side:

| Setting | Value |
|---|---|
| Root Directory | `frontend` |
| Framework Preset | Next.js |
| Build Command | *(default)* |

## 4. Checklist when something 404s or is blocked

| Symptom | Cause |
|---|---|
| `Request failed (404)` on sign-in | `NEXT_PUBLIC_API_URL` unset, or set but not redeployed |
| Sign-in works, photos are broken images | `NEXT_PUBLIC_API_URL` has a trailing slash or a typo |
| Browser console shows a CORS error | `CORS_ORIGINS` does not exactly match the frontend URL |
| QR code opens a page that will not load | `PUBLIC_BASE_URL` still says `localhost` |
| Uploads fail above a few MB | Uploads are going through a proxy instead of direct to the API |
| Guest camera button does nothing | The site is not on HTTPS; the camera API requires a secure origin |
