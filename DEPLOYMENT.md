# THE TARNISHED — Deployment Guide

This guide documents how to run and deploy **THE TARNISHED — Telugu Voice Crop
Advisory** as a connected prototype.

- Backend: FastAPI (`backend/`)
- Frontend: plain static HTML/CSS/JS (`frontend/`)
- Model: `models/maize_classifier.pkl` (FastAI, maize only)

---

## Architecture

```
[Web Frontend]  ──POST /predict──▶  [FastAPI Backend]
  static site                        │
                    GET /health ──────▶ (health check)
                    GET /audio/{f} ──▶ (Telugu voice)
                                     │
                       model.py · crop_stage.py · weather.py · advisory.py · voice.py
```

The backend has two independent entry points:
1. WhatsApp/Twilio webhook (`POST /twilio/webhook`),
2. Browser REST prediction (`POST /predict`).

Both reuse the same prediction/advisory pipeline and can run side by side.

---

## Local development

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows:   .venv\Scripts\activate
# Linux/mac: source .venv/bin/activate
pip install -r requirements.txt

# create your env file
cp .env.example .env   # then fill in Twilio values

python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

The FastAPI docs are then available at <http://localhost:8000/docs> — you can
test `POST /predict` there.

### 2. Frontend

Any static server works (the frontend has no build step):

```bash
cd frontend
python -m http.server 8080
```

Open <http://localhost:8080>.

If the backend is not on `http://localhost:8000`, set the API base URL by
adding a script before the others in `frontend/index.html`:

```html
<script>window.TARNISHED_API_BASE_URL = "https://your-backend.example";</script>
```

For the small "Prefer WhatsApp? Continue on WhatsApp →" link under the
Analyze button, set the public WhatsApp destination the same way:

```html
<script>window.TARNISHED_WHATSAPP_URL = "https://wa.me/91XXXXXXXXXX";</script>
```

Use the project's real `wa.me` chat link (or invite link). Until you set it,
the link stays hidden.

---

## Required environment variables (backend `.env`)

Copy `backend/.env.example` to `backend/.env`. All values are read from the
environment at startup.

| Variable                     | Required | Purpose                                                        |
| ---------------------------- | -------- | -------------------------------------------------------------- |
| `TWILIO_ACCOUNT_SID`         | yes*     | Twilio account SID for WhatsApp                                 |
| `TWILIO_AUTH_TOKEN`          | yes*     | Twilio auth token for WhatsApp                                  |
| `TWILIO_WHATSAPP_NUMBER`     | no       | WhatsApp number (has a sensible default)                        |
| `TWILIO_WHATSAPP_SANDBOX_CODE` | no     | WhatsApp sandbox join code (default set)                        |
| `PUBLIC_BASE_URL`            | yes      | Public backend URL (used for WhatsApp audio links in prod)      |
| `CORS_ALLOW_ORIGINS`         | no       | Comma-separated allowed frontend origin(s) for the web app      |
| `API_HOST`                   | no       | Bind host (default `0.0.0.0`)                                   |
| `API_PORT`                   | no       | Port (default `8000`)                                           |
| `DEBUG`                      | no       | `True`/`False`                                                  |

\* Required only to run the WhatsApp pipeline. The web `POST /predict` flow
does not need Twilio credentials (though the modules import the `twilio`
package, so it must still be installed).

> **Never commit a real `.env`.** `.gitignore` already excludes it. Only the
> `.env.example` template is committed.

---

## The model file

`models/maize_classifier.pkl` (~21 MB) is required by the backend and is kept
out of git. On any deployment target you must **upload it** to `models/`
separately. Do not delete or replace it — it is the trained maize model.

---

## CORS

The web frontend calls the backend from a different origin than the backend
itself, so CORS must allow the frontend origin.

- **Development:** leave `CORS_ALLOW_ORIGINS` empty — the backend allows
  `http://localhost:8080`, `http://127.0.0.1:8080`, `http://localhost:8000`,
  and `http://127.0.0.1:8000`.
- **Production:** set `CORS_ALLOW_ORIGINS` to your real frontend origin, e.g.
  `CORS_ALLOW_ORIGINS=https://crop-advisory.example.com`.

The WhatsApp webhook is unaffected by these CORS settings.

---

## Recommended deployment (simplest, no unnecessary infra)

Keep it minimal — no Docker/Kubernetes is required for this prototype.

### Option A — Two services (recommended)
- **Backend** on a platform that runs a long-lived Python service with
  environment variables and supports ~21 MB of static model upload, e.g.
  **Render** (web service), **Railway**, or **Fly.io**.
  - Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT` (run from
    `backend/`, set `PUBLIC_BASE_URL` to the platform's public URL).
- **Frontend** on any static host, e.g. **Netlify**, **Vercel**, **GitHub
  Pages**, or **Cloudflare Pages** (point the site root at `frontend/`, no build).
  - Set `window.TARNISHED_API_BASE_URL` to the backend's public URL.

### Option B — Single host
Run both on one server with a process manager: serve `frontend/` with Nginx and
run the backend with `uvicorn` (or gunicorn + uvicorn workers) behind Nginx.
Configure Nginx to reverse-proxy `/`, `/health`, `/predict`, `/audio/*`,
`/docs`, `/twilio/*` to the app.

---

## Verify a deployment

```bash
# health
curl https://<backend>/health

# unsupported crop is rejected
curl -F "image=@leaf.jpg" -F "crop=cotton" https://<backend>/predict   # -> 400

# predict with a maize image
curl -F "image=@leaf.jpg" -F "crop=maize" -F "sowing_date=2026-06-01" \
     -F "district=Warangal" https://<backend>/predict
```

Frontend health indicator uses `GET /health`; voice uses `GET /audio/{file}`.

---

## Git / secrets safety

- `do not commit` — after making changes, review with `git status` / `git diff`
  before committing.
- Confirm `.env`, `backend/.env` and generated `audio/*` are never committed.
- The committed `.env.example` contains only placeholders, no secrets.