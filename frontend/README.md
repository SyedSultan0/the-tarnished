# THE TARNISHED — Frontend

Clean, dependency-free frontend for **THE TARNISHED — Telugu Voice Crop Advisory**.

Built with plain HTML + CSS + JavaScript (no framework, no build step, no external
libraries). It talks directly to the existing FastAPI backend in `../backend`.

## Files

| File            | Purpose                                                        |
| --------------- | -------------------------------------------------------------- |
| `index.html`    | Landing screen, crop analysis form, loading & results UI      |
| `css/style.css` | Styling (clean agricultural theme, green accent, responsive)   |
| `js/api.js`     | API client layer (health check, prediction, audio resolution)  |
| `js/app.js`     | UI behavior (upload, validation, loading, results, voice)      |

## How to run

The frontend expects the backend to be reachable at `http://localhost:8000`
(the default in `js/api.js`).

1. Install backend dependencies and start the backend:

   ```bash
   cd backend
   pip install -r requirements.txt
   python -m uvicorn main:app --host 0.0.0.0 --port 8000
   ```

2. Serve the frontend folder (any static server works; e.g. Python):

   ```bash
   cd frontend
   python -m http.server 8080
   ```

3. Open <http://localhost:8080>.

To point the frontend at a different backend without editing code, set a global
before the scripts load:

```html
<script>window.TARNISHED_API_BASE_URL = "https://your-backend.example";</script>
```

In production, drop that `<script>` into `frontend/index.html` and set the API
URL to your real backend. No secrets belong in the frontend.

To enable the small "Prefer WhatsApp? Continue on WhatsApp →" link under the
Analyze button, set a second global **before** the scripts load (a default
pointing at the project's Twilio WhatsApp Sandbox number is already set in
`frontend/index.html`):

```html
<script>window.TARNISHED_WHATSAPP_URL = "https://wa.me/14155238886";</script>
```

Use the project's real public WhatsApp chat link (e.g. a `wa.me` link built
from the Twilio WhatsApp number, optionally with pre-filled text, or a group
invite link). Only `http(s)` links are accepted. When the value is missing or
empty the link stays hidden, so it never renders a broken link. No Twilio
SID/token or other secret belongs in the frontend.

## What works today (real backend endpoints)

- `GET /health` — shown as the "Service online / offline" status in the header.
- `GET /audio/{file}` — used by the voice player (`resolveAudioUrl`).
- `POST /predict` — the image diagnosis + advisory endpoint. Sends a
  multipart request with the image, crop, sowing date and location, and returns
  disease diagnosis, crop stage, weather risk, recommended action and a Telugu
  advisory (plus an audio URL).

> **Crop support:** the current trained model supports **maize only**. The form
> shows Crop = Maize (read-only) and the backend rejects any other crop.

## Prediction endpoint — `POST /predict`

Enabled in the backend by `backend/api/predict_router.py`. It reuses the
existing model, crop-stage, weather, advisory, and Telugu TTS modules.

### Expected request (sent by the frontend)

```
POST /predict
Content-Type: multipart/form-data

image        : file      (the uploaded crop photo)
crop         : string    (maize | cotton | paddy | chilli)
sowing_date  : string    (YYYY-MM-DD)
location     : string    (district name, optional)
district     : string    (district name, optional)
latitude     : number    (optional, derived from district on the client)
longitude    : number    (optional, derived from district on the client)
```

The frontend always sends `crop=maize`.

### Expected response (JSON) — what the frontend renders

```json
{
  "diagnosis": {
    "disease": "Gray_Leaf_Spot",
    "disease_display": "Gray Leaf Spot",
    "confidence": 0.861,
    "status": "high_confidence"
  },
  "crop_info": {
    "crop": "maize",
    "stage_name": "vegetative",
    "stage_description": "…",
    "days_since_sowing": 32,
    "days_until_harvest": 78,
    "progress_percentage": 29.0,
    "is_critical": false
  },
  "weather": {
    "risk_level": "moderate",
    "risk_score": 0.5,
    "summary": "…",
    "risk_factors": ["…"]
  },
  "advisory": {
    "action": "Apply fungicide spray",
    "product": "Azoxystrobin 23% SC",
    "dosage": "1.5 ml per liter of water",
    "timing": "At first symptom",
    "method": "Spray covering both sides of leaves",
    "safety_precautions": ["Wear mask and gloves"],
    "expected_result": "Controls infection within 7 days",
    "urgency": "Immediate",
    "stage_susceptibility": "…"
  },
  "telugu_advisory": "🌾 THE TARNISHED - పంట సలహా …",
  "audio_url": "/audio/advisory_xxxx.mp3"
}
```

`audio_url` may be absolute or relative (the frontend resolves relative URLs
against the backend base URL). Fields may be omitted; the UI only renders the
fields that are present.

### Error handling

The frontend maps backend failure states to human-readable messages:
- No image / invalid image / future sowing date — client-side validation.
- Network / timeout — "Could not reach the analysis service…".
- 400 / 422 — "service rejected the request…" (includes unsupported crop,
  invalid sowing date, unrecognized district).
- 500 — "service ran into an error…".
- 404 / 405 — "analysis service is not responding to this request…".