"""
predict_router.py - Browser REST Prediction Endpoint for THE TARNISHED

This module exposes a browser-callable `POST /predict` endpoint for the
web frontend. It ONLY orchestrates the existing THE TARNISHED pipeline:

    model.py      -> predict_maize
    crop_stage.py -> get_crop_stage
    weather.py    -> OpenMeteoClient / assess_weather_risk / get_telangana_coordinates
    advisory.py   -> get_advisory
    voice.py      -> generate_telugu_audio

It intentionally does NOT re-implement any of that logic. The WhatsApp /
Twilio webhook in `webhook_router.py` is left untouched and keeps working.

The current trained model supports MAIZE ONLY, so this endpoint accepts
`crop=maize` and rejects every other crop cleanly.
"""

from typing import Optional, Tuple

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from model import predict_maize
from weather import (
    OpenMeteoClient,
    assess_weather_risk,
    get_telangana_coordinates,
    validate_coordinates,
)
from crop_stage import get_crop_stage
from advisory import get_advisory
from voice import generate_telugu_audio
from api.webhook_router import (
    save_image,
    format_telugu_response,
)


router = APIRouter(tags=["Prediction"])


# ============================================================
# CONFIGURATION
# ============================================================

# The only crop the current trained model supports.
SUPPORTED_CROP = "maize"

# Shared weather client (mirrors the webhook's approach).
_weather_client = OpenMeteoClient()

# Values returned when a piece of context could not be resolved.
_UNAVAILABLE_WEATHER = {
    "risk_level": "low",
    "risk_score": 0,
    "risk_factors": [],
    "summary": "Weather data is unavailable for the provided location.",
}


# ============================================================
# REQUEST VALIDATION HELPERS
# ============================================================

def _validate_crop(crop: Optional[str]) -> str:
    """Validate that the requested crop is supported (maize only)."""
    requested = (crop or SUPPORTED_CROP).strip().lower()
    if requested != SUPPORTED_CROP:
        raise HTTPException(
            status_code=400,
            detail=(
                f"'{crop}' is not a supported crop. "
                "The current model only supports maize."
            ),
        )
    return requested


def _validate_image(upload: UploadFile) -> bytes:
    """Read and sanity-check the uploaded image."""
    if upload.content_type and not upload.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is not an image. Please upload a photo.",
        )

    image_bytes = upload.file.read()

    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="The uploaded image is empty. Please choose a valid photo.",
        )

    return image_bytes


def _resolve_coordinates(
    latitude: Optional[float],
    longitude: Optional[float],
    district: Optional[str],
    location: Optional[str],
) -> Optional[Tuple[float, float]]:
    """
    Resolve coordinates from whichever location fields the client sent.

    Priority:
      1. Explicit latitude/longitude (validated).
      2. A known Telangana district / location name.
      3. None (no location -> weather context treated as unavailable).
    """
    if latitude is not None and longitude is not None:
        valid, error = validate_coordinates(latitude, longitude)
        if not valid:
            raise HTTPException(status_code=400, detail=error)
        return latitude, longitude

    name = (district or location or "").strip()
    if not name:
        return None

    coords = get_telangana_coordinates(name)
    if coords is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"'{name}' is not a recognized Telangana district. "
                "Please choose a valid district name."
            ),
        )
    return coords


# ============================================================
# RESPONSE BUILDING HELPERS
# ============================================================

def _build_crop_info(stage_info: Optional[dict]) -> dict:
    """Normalise stage info into the frontend's crop_info contract."""
    if stage_info:
        info = dict(stage_info)
        info.setdefault("crop", SUPPORTED_CROP)
        return info

    return {
        "crop": SUPPORTED_CROP,
        "stage_name": None,
        "stage_description": "Sowing date was not provided.",
        "days_since_sowing": None,
        "days_until_harvest": None,
        "progress_percentage": None,
        "is_critical": False,
    }


def _build_weather(weather_risk: Optional[dict]) -> dict:
    """Normalise the weather risk assessment for the response."""
    if weather_risk:
        return weather_risk
    return dict(_UNAVAILABLE_WEATHER)


def _build_telugu_text(prediction, stage_info, weather_risk, advisory) -> str:
    """Reuse the existing Telugu response formatter from the webhook."""
    fallback_advisory = {
        "disease": prediction["disease"],
        "action": "Contact your local agricultural officer for expert guidance.",
        "product": None,
        "dosage": None,
        "timing": None,
        "method": None,
        "safety_precautions": [],
        "expected_result": None,
        "urgency": None,
        "stage_susceptibility": None,
    }
    used_advisory = advisory if advisory else fallback_advisory

    return format_telugu_response(
        disease=prediction["disease"],
        confidence=prediction["confidence"],
        stage_info=stage_info or {},
        weather_risk=weather_risk or _UNAVAILABLE_WEATHER,
        advisory=used_advisory,
    )


def _build_audio_url(telugu_text: str) -> Optional[str]:
    """Generate Telugu audio via the existing TTS and return a URL."""
    try:
        filename = generate_telugu_audio(telugu_text)
        return f"/audio/{filename}"
    except Exception:
        # TTS is best-effort; audio is optional compared to the text advisory.
        return None


# ============================================================
# PREDICT ENDPOINT
# ============================================================

@router.post(
    "/predict",
    summary="Predict crop disease and generate advisory",
)
async def predict(
    image: UploadFile = File(..., description="Crop photo (JPEG/PNG/WEBP)"),
    crop: Optional[str] = Form(SUPPORTED_CROP, description="Crop name"),
    sowing_date: Optional[str] = Form(None, description="Sowing date (YYYY-MM-DD)"),
    location: Optional[str] = Form(None, description="District / location name"),
    district: Optional[str] = Form(None, description="District name"),
    latitude: Optional[float] = Form(None, description="Latitude"),
    longitude: Optional[float] = Form(None, description="Longitude"),
):
    """
    Accept an uploaded crop image plus optional context (crop, sowing date,
    location) and return a JSON diagnosis + advisory compatible with the
    web frontend.

    Only `maize` is supported by the current model.
    """

    # ----------------------------------------------------------
    # 1. Validate inputs
    # ----------------------------------------------------------
    crop_value = _validate_crop(crop)
    image_bytes = _validate_image(image)
    coords = _resolve_coordinates(latitude, longitude, district, location)

    # ----------------------------------------------------------
    # 2. Crop-stage calculation (context, not prediction)
    # ----------------------------------------------------------
    stage_info: Optional[dict] = None
    if sowing_date:
        stage_info, stage_error = get_crop_stage(crop_value, sowing_date)
        if stage_error:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid sowing date: {stage_error} "
                    "Expected format YYYY-MM-DD."
                ),
            )

    # ----------------------------------------------------------
    # 3. Disease prediction (existing model)
    # ----------------------------------------------------------
    try:
        image_path = save_image(image_bytes)
        prediction = predict_maize(image_path)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail=(
                "The model could not process this image. "
                "Please try a clearer photo of the affected leaves."
            ),
        )

    # ----------------------------------------------------------
    # 4. Weather risk (context, optional)
    # ----------------------------------------------------------
    weather_risk: Optional[dict] = None
    if coords:
        try:
            context, weather_error = _weather_client.get_weather_context(
                coords[0], coords[1]
            )
            if context:
                risk = assess_weather_risk(context)
                risk["summary"] = _weather_client.get_weather_summary(context)
                weather_risk = risk
        except Exception:
            weather_risk = None

    # ----------------------------------------------------------
    # 5. Advisory (existing engine)
    # ----------------------------------------------------------
    crop_stage = (
        stage_info.get("stage_name", "unknown") if stage_info else "unknown"
    )
    advisory, advisory_error = get_advisory(
        disease=prediction["disease"],
        confidence=prediction["confidence"],
        crop=crop_value,
        crop_stage=crop_stage,
        weather_risk=weather_risk or _UNAVAILABLE_WEATHER,
        stage_info=stage_info or {},
    )

    if advisory_error:
        advisory = None

    disease_display = (
        advisory.get("disease", prediction["disease"])
        if advisory
        else prediction["disease"]
    )

    # ----------------------------------------------------------
    # 6. Telugu text + audio (existing formatter / TTS)
    # ----------------------------------------------------------
    telugu_text = _build_telugu_text(prediction, stage_info, weather_risk, advisory)
    audio_url = _build_audio_url(telugu_text)

    # ----------------------------------------------------------
    # 7. Build the frontend-compatible JSON response
    # ----------------------------------------------------------
    return {
        "diagnosis": {
            "disease": prediction["disease"],
            "disease_display": disease_display,
            "confidence": prediction["confidence"],
            "status": prediction["status"],
            "probabilities": prediction.get("probabilities", {}),
        },
        "crop_info": _build_crop_info(stage_info),
        "weather": _build_weather(weather_risk),
        "advisory": advisory,
        "telugu_advisory": telugu_text,
        "audio_url": audio_url,
    }