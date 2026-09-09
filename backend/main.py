"""
main.py - FastAPI Application for THE TARNISHED

This is the main entry point for the backend API.
Adapted from KrishiMitra-AI but modified for FastAI/PyTorch.

Key changes:
- Removed: TensorFlow/Keras warmup
- Removed: Gemini AI warmup
- Added: FastAI model warmup
- Added: Weather, Crop Stage, Advisory integration
- Added: Bilingual (Telugu/English) support
"""

import numpy as np
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

# Import routers and modules
from api import webhook_router
from core.config import settings

# Import our modules (will be created)
from model import learn as maize_model
from weather import get_weather_client
from crop_stage import CropStageCalculator
from advisory import AdvisoryEngine

# ------------------------------------------------------------------
# BILINGUAL MESSAGES (Telugu + English)
# ------------------------------------------------------------------

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

# ------------------------------------------------------------------
# CREATE FASTAPI APP
# ------------------------------------------------------------------

app = FastAPI(
    title="THE TARNISHED - Telugu Voice Crop Advisory",
    description="AI-powered crop disease advisory system for Telangana farmers",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ------------------------------------------------------------------
# CORS MIDDLEWARE (Allow frontend/WhatsApp access)
# ------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------
# APPLICATION STARTUP EVENT (Warm-up)
# ------------------------------------------------------------------

@app.on_event("startup")
def warmup_models():
    """
    Runs when the application starts to initialize models and prevent 
    cold-start timeouts on the first user request.
    """
    print("=" * 70)
    print("🌾 THE TARNISHED - Starting up... / ది టార్నిష్డ్ - ప్రారంభమవుతోంది...")
    print("=" * 70)
    
    # ------------------------------------------------------------------
    # 1. Warm up the FastAI Maize Disease Model
    # ------------------------------------------------------------------
    try:
        print("\n🔬 Loading Maize Disease Model... / మొక్కజొన్న వ్యాధి మోడల్ లోడ్ అవుతోంది...")
        if maize_model is not None:
            # Test with a dummy prediction to warm up
            dummy_image = np.zeros((224, 224, 3), dtype=np.uint8)
            from fastai.vision.all import PILImage
            dummy_pil = PILImage.create(dummy_image)
            
            # Run a dummy prediction
            pred, idx, probs = maize_model.predict(dummy_pil)
            print(f"   ✅ Maize Disease Model loaded successfully! / మొక్కజొన్న వ్యాధి మోడల్ విజయవంతంగా లోడ్ అయింది!")
            print(f"   📊 Model ready for inference / మోడల్ అంచనా కోసం సిద్ధంగా ఉంది")
        else:
            print("   ⚠️ Maize Disease Model not found. / మొక్కజొన్న వ్యాధి మోడల్ కనుగొనబడలేదు.")
    except Exception as e:
        print(f"   ❌ Could not warm up Maize Disease Model: {e}")
    
    # ------------------------------------------------------------------
    # 2. Initialize Weather Client (No API key needed)
    # ------------------------------------------------------------------
    try:
        print("\n🌤️ Initializing Weather Client... / వాతావరణ క్లయింట్ ప్రారంభమవుతోంది...")
        weather_client = get_weather_client()
        print("   ✅ Weather Client initialized (Open-Meteo) / వాతావరణ క్లయింట్ సిద్ధంగా ఉంది")
    except Exception as e:
        print(f"   ⚠️ Could not initialize Weather Client: {e}")
    
    # ------------------------------------------------------------------
    # 3. Initialize Crop Stage Calculator
    # ------------------------------------------------------------------
    try:
        print("\n🌱 Initializing Crop Stage Calculator... / పంట దశ కాలిక్యులేటర్ ప్రారంభమవుతోంది...")
        crop_calculator = CropStageCalculator()
        print(f"   ✅ Crop Stage Calculator initialized / పంట దశ కాలిక్యులేటర్ సిద్ధంగా ఉంది")
        print(f"   📋 Supported crops: {', '.join(settings.SUPPORTED_CROPS)}")
    except Exception as e:
        print(f"   ⚠️ Could not initialize Crop Stage Calculator: {e}")
    
    # ------------------------------------------------------------------
    # 4. Initialize Advisory Engine
    # ------------------------------------------------------------------
    try:
        print("\n📋 Initializing Advisory Engine... / సలహా ఇంజిన్ ప్రారంభమవుతోంది...")
        advisory_engine = AdvisoryEngine()
        print(f"   ✅ Advisory Engine initialized / సలహా ఇంజిన్ సిద్ధంగా ఉంది")
        print(f"   📋 Supported diseases: Common_Rust, Gray_Leaf_Spot, NCLB, Healthy")
    except Exception as e:
        print(f"   ⚠️ Could not initialize Advisory Engine: {e}")
    
    # ------------------------------------------------------------------
    # 5. Print Configuration Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("📊 CONFIGURATION SUMMARY / కాన్ఫిగరేషన్ సారాంశం")
    print("=" * 70)
    print(f"   Model Path / మోడల్ మార్గం: {settings.MODEL_PATH}")
    print(f"   WhatsApp Number / WhatsApp నంబర్: {settings.TWILIO_WHATSAPP_NUMBER}")
    print(f"   Confidence Threshold / నమ్మకం పరిమితి: {settings.HIGH_CONFIDENCE_THRESHOLD}")
    print(f"   Default Crop / డిఫాల్ట్ పంట: {settings.DEFAULT_CROP}")
    print(f"   Debug Mode / డీబగ్ మోడ్: {settings.DEBUG}")
    print("=" * 70)
    print(f"✅ {HEALTHY_MESSAGES['en']}")
    print(f"✅ {HEALTHY_MESSAGES['te']}")
    print("=" * 70)


# ------------------------------------------------------------------
# APPLICATION SHUTDOWN EVENT
# ------------------------------------------------------------------

@app.on_event("shutdown")
def shutdown():
    """Cleanup on application shutdown"""
    print("\n🛑 THE TARNISHED shutting down...")
    print(f"👋 {SHUTDOWN_MESSAGES['en']}")
    print(f"👋 {SHUTDOWN_MESSAGES['te']}")


# ------------------------------------------------------------------
# HEALTH CHECK ENDPOINTS (Bilingual)
# ------------------------------------------------------------------

@app.get("/", tags=["Health Check"])
def read_root():
    """Root endpoint - health check with bilingual response"""
    return {
        "status": "ok",
        "message_en": STATUS_MESSAGES["en"],
        "message_te": STATUS_MESSAGES["te"],
        "version": "1.0.0",
        "crops_supported": settings.SUPPORTED_CROPS,
        "crops_supported_te": ["మొక్కజొన్న", "పత్తి", "వరి", "మిరప"],
        "model_loaded": maize_model is not None
    }


@app.get("/health", tags=["Health Check"])
def health_check():
    """Detailed health check endpoint with bilingual response"""
    return {
        "status": "healthy",
        "status_te": "ఆరోగ్యంగా ఉంది",
        "model": "loaded" if maize_model is not None else "not_loaded",
        "model_te": "లోడ్ అయింది" if maize_model is not None else "లోడ్ కాలేదు",
        "twilio_configured": bool(settings.TWILIO_ACCOUNT_SID),
        "twilio_configured_te": "కాన్ఫిగర్ చేయబడింది" if settings.TWILIO_ACCOUNT_SID else "కాన్ఫిగర్ చేయబడలేదు",
        "weather": "configured",
        "weather_te": "కాన్ఫిగర్ చేయబడింది",
        "crops": settings.SUPPORTED_CROPS,
        "crops_te": ["మొక్కజొన్న", "పత్తి", "వరి", "మిరప"],
        "confidence_threshold": settings.HIGH_CONFIDENCE_THRESHOLD
    }


@app.get("/welcome", tags=["Health Check"])
def welcome():
    """Welcome endpoint with full bilingual greeting"""
    return {
        "welcome": {
            "en": "🌾 Welcome to THE TARNISHED - AI Crop Advisory System",
            "te": "🌾 ది టార్నిష్డ్ కి స్వాగతం - AI పంట సలహా వ్యవస్థ"
        },
        "description": {
            "en": "Send a photo of your crop via WhatsApp to get disease diagnosis and advisory in Telugu voice",
            "te": "మీ పంట ఫోటోను WhatsApp ద్వారా పంపండి - తెలుగు వాయిస్లో వ్యాధి నిర్ధారణ మరియు సలహా పొందండి"
        },
        "how_to_use": {
            "en": "1. Send 'join twilio-trial' to +1 (737) 250-8034\n2. Send a photo of your crop\n3. Receive advisory in Telugu voice",
            "te": "1. '+1 (737) 250-8034' కు 'join twilio-trial' పంపండి\n2. మీ పంట ఫోటోను పంపండి\n3. తెలుగు వాయిస్లో సలహా పొందండి"
        },
        "supported_crops": {
            "en": ["Maize", "Cotton", "Paddy", "Chilli"],
            "te": ["మొక్కజొన్న", "పత్తి", "వరి", "మిరప"]
        }
    }


# ------------------------------------------------------------------
# TWILIO ERROR WEBHOOK (For debugging)
# ------------------------------------------------------------------

@app.post("/twilio/error", tags=["Twilio Webhook"])
async def twilio_error_webhook(request: Request):
    """
    Twilio Debugger webhook for error logging.
    Accepts both JSON and form-encoded payloads.
    """
    ctype = request.headers.get("content-type", "")
    payload = {}

    try:
        if "application/json" in ctype.lower():
            payload = await request.json()
        else:
            form = await request.form()
            payload = dict(form)
    except Exception as e:
        raw = (await request.body())[:2000]
        print("[TWILIO DEBUGGER RAW]", raw)
        print("[TWILIO DEBUGGER PARSE ERROR]", e)

    print("[TWILIO DEBUGGER PAYLOAD]", payload)
    return {"status": "received"}


# ------------------------------------------------------------------
# INCLUDE ROUTERS
# ------------------------------------------------------------------

# Include the WhatsApp webhook router
app.include_router(
    webhook_router.router,
    prefix="/twilio",
    tags=["Twilio Webhook"]
)


# ------------------------------------------------------------------
# MAIN ENTRY POINT (for local testing)
# ------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Starting THE TARNISHED server...")
    print("🚀 ది టార్నిష్డ్ సర్వర్ ప్రారంభమవుతోంది...")
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG
    )