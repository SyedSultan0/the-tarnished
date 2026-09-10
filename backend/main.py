"""
main.py - FastAPI Application for THE TARNISHED

Main entry point for the backend API.
"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import numpy as np

from api import webhook_router
from api import predict_router
from core.config import settings

from model import predict_maize, torch_model as maize_model
from weather import get_weather_client
from crop_stage import CropStageCalculator
from advisory import AdvisoryEngine


# ==============================================================
# BILINGUAL MESSAGES
# ==============================================================

WELCOME_MESSAGES = {
    "en": "🌾 THE TARNISHED - Telugu Voice Crop Advisory",
    "te": "🌾 ది టార్నిష్డ్ - తెలుగు వాయిస్ పంట సలహా"
}

DESCRIPTION_MESSAGES = {
    "en": "AI-powered crop disease advisory system for Telangana farmers",
    "te": "తెలంగాణ రైతుల కోసం AI ఆధారిత పంట వ్యాధి సలహా వ్యవస్థ"
}

HEALTHY_MESSAGES = {
    "en": "✅ THE TARNISHED is ready! 🚀",
    "te": "✅ ది టార్నిష్డ్ సిద్ధంగా ఉంది! 🚀"
}

SHUTDOWN_MESSAGES = {
    "en": "👋 THE TARNISHED shutting down... Goodbye!",
    "te": "👋 ది టార్నిష్డ్ మూసివేయబడుతోంది... వీడ్కోలు!"
}

STATUS_MESSAGES = {
    "en": "🌾 THE TARNISHED - Telugu Voice Crop Advisory",
    "te": "🌾 ది టార్నిష్డ్ - తెలుగు వాయిస్ పంట సలహా"
}


# ==============================================================
# CREATE FASTAPI APP
# ==============================================================

app = FastAPI(
    title="THE TARNISHED - Telugu Voice Crop Advisory",
    description="AI-powered crop disease advisory system for Telangana farmers",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)


# ==============================================================
# SERVE GENERATED TELUGU AUDIO
# ==============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

AUDIO_DIR = BASE_DIR / "audio"

AUDIO_DIR.mkdir(exist_ok=True)

app.mount(
    "/audio",
    StaticFiles(directory=AUDIO_DIR),
    name="audio"
)


# ==============================================================
# CORS MIDDLEWARE
# ==============================================================

# Allowed origins come from the CORS_ALLOW_ORIGINS environment variable
# (comma-separated). A safe localhost development default is used when the
# variable is unset so the web frontend works out of the box in dev.
if settings.CORS_ALLOW_ORIGINS:
    allowed_origins = [
        origin.strip()
        for origin in settings.CORS_ALLOW_ORIGINS.split(",")
        if origin.strip()
    ]
else:
    allowed_origins = [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================
# APPLICATION STARTUP
# ==============================================================

@app.on_event("startup")
def warmup_models():

    print("=" * 70)

    print(
        "🌾 THE TARNISHED - Starting up..."
    )

    print(
        "🌾 ది టార్నిష్డ్ - ప్రారంభమవుతోంది..."
    )

    print("=" * 70)


    # ==========================================================
    # 1. WARM UP MAIZE MODEL
    # ==========================================================

    try:

        print(
            "\n🔬 Loading Maize Disease Model..."
        )

        print(
            "మొక్కజొన్న వ్యాధి మోడల్ లోడ్ అవుతోంది..."
        )

        if maize_model is not None:

            from PIL import Image as PILImage

            dummy_image = np.zeros(
                (224, 224, 3),
                dtype=np.uint8
            )

            dummy_pil = PILImage.fromarray(
                dummy_image
            )

            predict_maize(
                dummy_pil
            )

            print(
                "   ✅ Maize Disease Model loaded successfully!"
            )

            print(
                "   📊 Model ready for inference"
            )

        else:

            print(
                "   ⚠️ Maize Disease Model not found."
            )

    except Exception as e:

        print(
            f"   ❌ Could not warm up "
            f"Maize Disease Model: {e}"
        )


    # ==========================================================
    # 2. INITIALIZE WEATHER CLIENT
    # ==========================================================

    try:

        print(
            "\n🌤️ Initializing Weather Client..."
        )

        print(
            "వాతావరణ క్లయింట్ ప్రారంభమవుతోంది..."
        )

        weather_client = get_weather_client()

        print(
            "   ✅ Weather Client initialized "
            "(Open-Meteo)"
        )

    except Exception as e:

        print(
            f"   ⚠️ Could not initialize "
            f"Weather Client: {e}"
        )


    # ==========================================================
    # 3. INITIALIZE CROP STAGE CALCULATOR
    # ==========================================================

    try:

        print(
            "\n🌱 Initializing Crop Stage Calculator..."
        )

        print(
            "పంట దశ కాలిక్యులేటర్ ప్రారంభమవుతోంది..."
        )

        crop_calculator = CropStageCalculator()

        print(
            "   ✅ Crop Stage Calculator initialized"
        )

        print(
            f"   📋 Supported crops: "
            f"{', '.join(settings.SUPPORTED_CROPS)}"
        )

    except Exception as e:

        print(
            f"   ⚠️ Could not initialize "
            f"Crop Stage Calculator: {e}"
        )


    # ==========================================================
    # 4. INITIALIZE ADVISORY ENGINE
    # ==========================================================

    try:

        print(
            "\n📋 Initializing Advisory Engine..."
        )

        print(
            "సలహా ఇంజిన్ ప్రారంభమవుతోంది..."
        )

        advisory_engine = AdvisoryEngine()

        print(
            "   ✅ Advisory Engine initialized"
        )

        print(
            "   📋 Supported diseases: "
            "Common_Rust, Gray_Leaf_Spot, "
            "NCLB, Healthy"
        )

    except Exception as e:

        print(
            f"   ⚠️ Could not initialize "
            f"Advisory Engine: {e}"
        )


    # ==========================================================
    # 5. CONFIGURATION SUMMARY
    # ==========================================================

    print(
        "\n" + "=" * 70
    )

    print(
        "📊 CONFIGURATION SUMMARY"
    )

    print(
        "కాన్ఫిగరేషన్ సారాంశం"
    )

    print("=" * 70)

    print(
        f"   Model Path: "
        f"{settings.MODEL_PATH}"
    )

    print(
        f"   WhatsApp Number: "
        f"{settings.TWILIO_WHATSAPP_NUMBER}"
    )

    print(
        f"   Confidence Threshold: "
        f"{settings.HIGH_CONFIDENCE_THRESHOLD}"
    )

    print(
        f"   Default Crop: "
        f"{settings.DEFAULT_CROP}"
    )

    print(
        f"   Debug Mode: "
        f"{settings.DEBUG}"
    )

    print("=" * 70)

    print(
        f"✅ {HEALTHY_MESSAGES['en']}"
    )

    print(
        f"✅ {HEALTHY_MESSAGES['te']}"
    )

    print("=" * 70)


# ==============================================================
# APPLICATION SHUTDOWN
# ==============================================================

@app.on_event("shutdown")
def shutdown():

    print(
        "\n🛑 THE TARNISHED shutting down..."
    )

    print(
        f"👋 {SHUTDOWN_MESSAGES['en']}"
    )

    print(
        f"👋 {SHUTDOWN_MESSAGES['te']}"
    )


# ==============================================================
# ROOT HEALTH CHECK
# ==============================================================

@app.get(
    "/",
    tags=["Health Check"]
)
def read_root():

    return {

        "status": "ok",

        "message_en": STATUS_MESSAGES["en"],

        "message_te": STATUS_MESSAGES["te"],

        "version": "1.0.0",

        "crops_supported": settings.SUPPORTED_CROPS,

        "crops_supported_te": [
            "మొక్కజొన్న",
            "పత్తి",
            "వరి",
            "మిరప"
        ],

        "model_loaded": maize_model is not None
    }


# ==============================================================
# DETAILED HEALTH CHECK
# ==============================================================

@app.get(
    "/health",
    tags=["Health Check"]
)
def health_check():

    return {

        "status": "healthy",

        "status_te": "ఆరోగ్యంగా ఉంది",

        "model": (
            "loaded"
            if maize_model is not None
            else "not_loaded"
        ),

        "model_te": (
            "లోడ్ అయింది"
            if maize_model is not None
            else "లోడ్ కాలేదు"
        ),

        "twilio_configured": bool(
            settings.TWILIO_ACCOUNT_SID
        ),

        "twilio_configured_te": (
            "కాన్ఫిగర్ చేయబడింది"
            if settings.TWILIO_ACCOUNT_SID
            else "కాన్ఫిగర్ చేయబడలేదు"
        ),

        "weather": "configured",

        "weather_te": "కాన్ఫిగర్ చేయబడింది",

        "crops": settings.SUPPORTED_CROPS,

        "crops_te": [
            "మొక్కజొన్న",
            "పత్తి",
            "వరి",
            "మిరప"
        ],

        "confidence_threshold":
            settings.HIGH_CONFIDENCE_THRESHOLD
    }


# ==============================================================
# WELCOME ENDPOINT
# ==============================================================

@app.get(
    "/welcome",
    tags=["Health Check"]
)
def welcome():

    return {

        "welcome": {

            "en":
                "🌾 Welcome to THE TARNISHED - "
                "AI Crop Advisory System",

            "te":
                "🌾 ది టార్నిష్డ్ కి స్వాగతం - "
                "AI పంట సలహా వ్యవస్థ"
        },

        "description": {

            "en":
                "Send a photo of your crop via WhatsApp "
                "to get disease diagnosis and advisory "
                "in Telugu voice",

            "te":
                "మీ పంట ఫోటోను WhatsApp ద్వారా పంపండి - "
                "తెలుగు వాయిస్లో వ్యాధి నిర్ధారణ "
                "మరియు సలహా పొందండి"
        },

        "how_to_use": {

            "en":
                "1. Send 'join twilio-trial' to "
                "+1 (737) 250-8034\n"
                "2. Send a photo of your crop\n"
                "3. Receive advisory in Telugu voice",

            "te":
                "1. '+1 (737) 250-8034' కు "
                "'join twilio-trial' పంపండి\n"
                "2. మీ పంట ఫోటోను పంపండి\n"
                "3. తెలుగు వాయిస్లో సలహా పొందండి"
        },

        "supported_crops": {

            "en": [
                "Maize",
                "Cotton",
                "Paddy",
                "Chilli"
            ],

            "te": [
                "మొక్కజొన్న",
                "పత్తి",
                "వరి",
                "మిరప"
            ]
        }
    }


# ==============================================================
# TWILIO ERROR WEBHOOK
# ==============================================================

@app.post(
    "/twilio/error",
    tags=["Twilio Webhook"]
)
async def twilio_error_webhook(
    request: Request
):

    payload = {}

    content_type = request.headers.get(
        "content-type",
        ""
    )

    try:

        if "application/json" in content_type.lower():

            payload = await request.json()

        else:

            form = await request.form()

            payload = dict(form)

    except Exception as e:

        raw = (
            await request.body()
        )[:2000]

        print(
            "[TWILIO DEBUGGER RAW]",
            raw
        )

        print(
            "[TWILIO DEBUGGER PARSE ERROR]",
            e
        )

    print(
        "[TWILIO DEBUGGER PAYLOAD]",
        payload
    )

    return {
        "status": "received"
    }


# ==============================================================
# INCLUDE WHATSAPP ROUTER
# ==============================================================

app.include_router(

    webhook_router.router,

    prefix="/twilio",

    tags=["Twilio Webhook"]
)


# ==============================================================
# INCLUDE PREDICT ROUTER (Browser REST API)
# ==============================================================

app.include_router(
    predict_router.router,
    tags=["Prediction"]
)


# ==============================================================
# MAIN ENTRY POINT
# ==============================================================

if __name__ == "__main__":

    import uvicorn

    print(
        "🚀 Starting THE TARNISHED server..."
    )

    print(
        "🚀 ది టార్నిష్డ్ సర్వర్ ప్రారంభమవుతోంది..."
    )

    uvicorn.run(

        "main:app",

        host=settings.API_HOST,

        port=settings.API_PORT,

        reload=settings.DEBUG
    )