from fastapi import APIRouter, Request
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client

from pathlib import Path
from datetime import datetime
import re
import traceback
import requests

from core.config import settings

from model import predict_maize
from weather import (
    OpenMeteoClient,
    assess_weather_risk,
    get_telangana_coordinates
)
from crop_stage import get_crop_stage
from advisory import get_advisory
from voice import generate_telugu_audio


# ============================================================
# ROUTER
# ============================================================

router = APIRouter()


# ============================================================
# SESSION STORAGE
# ============================================================

# Temporary in-memory session storage.
# Later this can be replaced by Redis / database.
sessions = {}


def get_session(phone_number: str) -> dict:
    if phone_number not in sessions:
        sessions[phone_number] = {
            "crop": "maize",
            "sowing_date": None,
            "district": None,
            "latitude": None,
            "longitude": None,
            # Tracks whether the beginner-friendly welcome/instruction
            # message has already been sent in this session store.
            # In-memory only; resets on backend restart (same as the
            # rest of the session state).
            "welcomed": False,
        }

    return sessions[phone_number]


# ============================================================
# WHATSAPP WELCOME MESSAGE
# ============================================================

# Short, beginner-friendly instruction sent once when a new WhatsApp
# user first interacts with the bot. Sowing date / location are framed
# as optional because the pipeline still works without them.
WELCOME_MESSAGE = (
    "🌱 Welcome to The Tarnished!\n\n"
    "📸 Send a clear photo of your maize leaf to check for disease.\n\n"
    "For a more useful advisory, you can also send:\n"
    "📅 Your sowing date (e.g. 01/07/2026)\n"
    "📍 Your district/location\n\n"
    "I'll identify the disease and tell you what action to take."
)

# Short texts treated as a greeting / bot-start attempt.
GREETING_KEYWORDS = frozenset({
    "hi",
    "hello",
    "hey",
    "namaste",
    "namastey",
    "start",
    "join",
    "help",
    "menu",
    "bot",
    "hai",
})


def is_greeting(text: str) -> bool:
    """Return True when the message looks like a greeting/bot-start."""
    if not text:
        return False
    cleaned = re.sub(r"[^a-z ]", "", text.lower()).strip()
    if not cleaned:
        return False
    if cleaned in GREETING_KEYWORDS:
        return True
    first_word = cleaned.split()[0] if cleaned.split() else ""
    return first_word in GREETING_KEYWORDS


# ============================================================
# TWILIO CLIENT
# ============================================================

twilio_client = Client(
    settings.TWILIO_ACCOUNT_SID,
    settings.TWILIO_AUTH_TOKEN
)


# ============================================================
# WEATHER CLIENT
# ============================================================

weather_client_instance = OpenMeteoClient()


# ============================================================
# HELPERS
# ============================================================

def extract_sowing_date(text: str):
    """
    Extract a date from farmer's message.

    Supported:
    DD/MM/YYYY
    DD-MM-YYYY
    DD.MM.YYYY
    YYYY-MM-DD

    Examples:
    01/06/2026
    01-06-2026
    2026-06-01
    """

    if not text:
        return None

    patterns = [
        r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})",
        r"(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)

        if not match:
            continue

        groups = match.groups()

        try:
            # YYYY-MM-DD
            if len(groups[0]) == 4:
                year, month, day = map(int, groups)

            # DD-MM-YYYY
            else:
                day, month, year = map(int, groups)

            date_obj = datetime(
                year,
                month,
                day
            )

            return date_obj.strftime("%Y-%m-%d")

        except ValueError:
            return None

    return None


def extract_crop(text: str):
    """
    Extract crop from message.
    """

    if not text:
        return None

    text_lower = text.lower()

    crops = [
        "maize",
        "cotton",
        "paddy",
        "chilli"
    ]

    for crop in crops:
        if crop in text_lower:
            return crop

    return None


def get_location_from_text(text: str):
    """
    Extract Telangana district from farmer message.

    Example:
    Hyderabad
    Warangal
    Karimnagar
    Nizamabad
    etc.
    """

    if not text:
        return None

    text_lower = text.lower().strip()

    # Use the complete district list from weather.py
    districts = [
        "hyderabad",
        "warangal",
        "nizamabad",
        "khammam",
        "karimnagar",
        "mahabubnagar",
        "adilabad",
        "nalgonda",
        "sangareddy",
        "medak",
        "siddipet",
        "jagtial",
        "mancherial",
        "peddapalli",
        "kamareddy",
        "bhongir",
        "suryapet",
        "jangaon",
        "gadwal",
        "nagarkurnool",
        "vikarabad",
        "yadadri",
    ]

    for district in districts:
        if district in text_lower:
            coordinates = get_telangana_coordinates(district)

            if coordinates:
                return {
                    "district": district,
                    "latitude": coordinates[0],
                    "longitude": coordinates[1],
                }

    return None


def extract_lat_lon(text: str):
    """
    Optional direct latitude/longitude support.

    Example:
    17.385, 78.4867
    """

    if not text:
        return None

    pattern = r"(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)"

    match = re.search(pattern, text)

    if not match:
        return None

    try:
        latitude = float(match.group(1))
        longitude = float(match.group(2))

        if (
            -90 <= latitude <= 90
            and -180 <= longitude <= 180
        ):
            return {
                "latitude": latitude,
                "longitude": longitude,
            }

    except ValueError:
        pass

    return None


def download_twilio_image(media_url: str):
    """
    Download image sent through WhatsApp/Twilio.
    """

    try:
        response = requests.get(
            media_url,
            auth=(
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN
            ),
            timeout=30
        )

        response.raise_for_status()

        return response.content

    except Exception as error:
        print(
            f"❌ Image download failed: {error}"
        )

        return None


def save_image(image_bytes: bytes):
    """
    Save downloaded image temporarily.
    """

    image_dir = (
        Path(__file__).resolve().parent.parent
        / "temp_images"
    )

    image_dir.mkdir(
        exist_ok=True
    )

    filename = (
        f"crop_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        f".jpg"
    )

    image_path = image_dir / filename

    with open(
        image_path,
        "wb"
    ) as file:
        file.write(image_bytes)

    return image_path


# ============================================================
# RESPONSE FORMATTING
# ============================================================

def format_english_response(
    disease: str,
    confidence: float,
    stage_info: dict,
    weather_risk: dict,
    advisory: dict
):
    """
    Build farmer-facing English advisory.
    """

    stage = stage_info.get(
        "stage_name",
        "unknown"
    )

    risk_level = weather_risk.get(
        "risk_level",
        "low"
    )

    safety = advisory.get(
        "safety_precautions",
        []
    )

    safety_text = ""

    for item in safety:
        safety_text += f"• {item}\n"

    return (
        "🌾 THE TARNISHED - Crop Advisory\n\n"

        f"🔬 Disease: {disease}\n"
        f"📊 Confidence: {confidence * 100:.1f}%\n"
        f"🌱 Crop stage: {stage}\n"
        f"🌤️ Weather risk: {risk_level}\n\n"

        "📝 RECOMMENDED ACTION:\n"
        f"• Action: {advisory.get('action', 'Not available')}\n"
        f"• Product: {advisory.get('product', 'Not applicable')}\n"
        f"• Dosage: {advisory.get('dosage', 'Not applicable')}\n"
        f"• Timing: {advisory.get('timing', 'Not specified')}\n"
        f"• Method: {advisory.get('method', 'Not specified')}\n\n"

        "⚠️ SAFETY:\n"
        f"{safety_text}\n"

        f"📈 Expected result: "
        f"{advisory.get('expected_result', 'Not specified')}\n\n"

        f"⏰ Urgency: "
        f"{advisory.get('urgency', 'Not specified')}"
    )


def format_telugu_response(
    disease: str,
    confidence: float,
    stage_info: dict,
    weather_risk: dict,
    advisory: dict
):
    """
    Telugu farmer-facing response.

    This is intentionally kept simple because this text
    is also sent to the Telugu TTS engine.
    """

    stage = stage_info.get(
        "stage_name",
        "తెలియదు"
    )

    risk_level = weather_risk.get(
        "risk_level",
        "low"
    )

    risk_translation = {
        "low": "తక్కువ",
        "medium": "మధ్యస్థం",
        "high": "అధిక"
    }

    risk_telugu = risk_translation.get(
        risk_level,
        risk_level
    )

    safety = advisory.get(
        "safety_precautions",
        []
    )

    safety_text = ""

    for item in safety:
        safety_text += f"• {item}\n"

    # Disease names are kept readable.
    # Later these can be replaced by proper Telugu names.
    disease_names = {
        "Common_Rust": "Common Rust",
        "Gray_Leaf_Spot": "Gray Leaf Spot",
        "Northern_Corn_Leaf_Blight":
            "Northern Corn Leaf Blight",
        "Healthy": "Healthy Plant",
    }

    disease_display = disease_names.get(
        disease,
        disease
    )

    return (
        "🌾 THE TARNISHED - పంట సలహా\n\n"

        f"🔬 వ్యాధి: {disease_display}\n"
        f"📊 నమ్మక స్థాయి: {confidence * 100:.1f}%\n"
        f"🌱 పంట దశ: {stage}\n"
        f"🌤️ వాతావరణ ప్రమాదం: {risk_telugu}\n\n"

        "📝 చేయవలసిన చర్య:\n"
        f"• చర్య: {advisory.get('action', 'సమాచారం లేదు')}\n"
        f"• మందు: {advisory.get('product', 'వర్తించదు')}\n"
        f"• మోతాదు: {advisory.get('dosage', 'వర్తించదు')}\n"
        f"• సమయం: {advisory.get('timing', 'సూచించలేదు')}\n"
        f"• విధానం: {advisory.get('method', 'సూచించలేదు')}\n\n"

        "⚠️ జాగ్రత్తలు:\n"
        f"{safety_text}\n"

        f"📈 ఆశించిన ఫలితం: "
        f"{advisory.get('expected_result', 'సూచించలేదు')}\n\n"

        f"⏰ అత్యవసరత: "
        f"{advisory.get('urgency', 'సూచించలేదు')}"
    )


# ============================================================
# MAIN WHATSAPP WEBHOOK
# ============================================================

@router.post("/webhook")
async def whatsapp_webhook(request: Request):

    response_twiml = MessagingResponse()

    try:

        # ----------------------------------------------------
        # READ FORM DATA
        # ----------------------------------------------------

        form = await request.form()

        from_number = form.get(
            "From",
            ""
        )

        body = form.get(
            "Body",
            ""
        )

        media_url = form.get(
            "MediaUrl0"
        )

        media_content_type = form.get(
            "MediaContentType0"
        )

        print("\n" + "=" * 60)
        print("📩 WhatsApp message received")
        print(f"👤 From: {from_number}")
        print(f"💬 Message: {body}")
        print(f"📎 Media: {media_url}")
        print("=" * 60)

        # ----------------------------------------------------
        # GET SESSION
        # ----------------------------------------------------

        session = get_session(
            from_number
        )

        # WELCOME UX (new user or greeting)
        # ----------------------------------------------------
        # First-ever message from this number, or any later
        # greeting-like message, gets the short instruction text
        # prepended to the normal reply. The prediction/advisory
        # flow below is unchanged.
        needs_welcome = (
            not session.get("welcomed", False)
            or is_greeting(body)
        )
        if needs_welcome:
            session["welcomed"] = True

        def with_welcome(text):
            if needs_welcome and text:
                return WELCOME_MESSAGE + "\n\n" + text
            if needs_welcome:
                return WELCOME_MESSAGE
            return text

        # EXTRACT CROP
        # ----------------------------------------------------

        detected_crop = extract_crop(
            body
        )

        if detected_crop:
            session["crop"] = detected_crop

            print(
                f"🌾 Crop detected: "
                f"{detected_crop}"
            )

        crop = session.get(
            "crop",
            "maize"
        )

        # ----------------------------------------------------
        # EXTRACT SOWING DATE
        # ----------------------------------------------------

        detected_sowing_date = extract_sowing_date(
            body
        )

        if detected_sowing_date:

            session["sowing_date"] = (
                detected_sowing_date
            )

            print(
                f"📅 Sowing date: "
                f"{detected_sowing_date}"
            )

        # ----------------------------------------------------
        # EXTRACT LOCATION
        # ----------------------------------------------------

        location = get_location_from_text(
            body
        )

        if location:

            session["district"] = (
                location["district"]
            )

            session["latitude"] = (
                location["latitude"]
            )

            session["longitude"] = (
                location["longitude"]
            )

            print(
                f"📍 Location: "
                f"{location['district']} "
                f"({location['latitude']}, "
                f"{location['longitude']})"
            )

        # ----------------------------------------------------
        # DIRECT LAT/LON
        # ----------------------------------------------------

        lat_lon = extract_lat_lon(
            body
        )

        if lat_lon:

            session["latitude"] = (
                lat_lon["latitude"]
            )

            session["longitude"] = (
                lat_lon["longitude"]
            )

            print(
                f"📍 Coordinates: "
                f"{lat_lon['latitude']}, "
                f"{lat_lon['longitude']}"
            )

        # ----------------------------------------------------
        # NO IMAGE
        # ----------------------------------------------------

        if not media_url:

            message = (
                "🌾 THE TARNISHED\n\n"
                "Please send a clear photo of your "
                "maize leaf along with your sowing "
                "date and district.\n\n"

                "Example:\n"
                "Crop: maize\n"
                "Sowing date: 01/06/2026\n"
                "District: Hyderabad"
            )

            response_twiml.message(
                with_welcome(message)
            )

            return Response(
                content=str(response_twiml),
                media_type="application/xml"
            )

        # ----------------------------------------------------
        # IMAGE RECEIVED
        # ----------------------------------------------------

        print("📸 Image received")

        image_bytes = download_twilio_image(
            media_url
        )

        if not image_bytes:

            response_twiml.message(
                with_welcome(
                    "❌ I could not download the image. "
                    "Please send the photo again."
                )
            )

            return Response(
                content=str(response_twiml),
                media_type="application/xml"
            )

        print(
            "✅ Image downloaded"
        )

        # ----------------------------------------------------
        # SAVE IMAGE
        # ----------------------------------------------------

        image_path = save_image(
            image_bytes
        )

        print(
            f"💾 Image saved: "
            f"{image_path}"
        )

        # ----------------------------------------------------
        # DISEASE PREDICTION
        # ----------------------------------------------------

        prediction = predict_maize(
            image_path
        )

        disease = prediction[
            "disease"
        ]

        confidence = prediction[
            "confidence"
        ]

        status = prediction[
            "status"
        ]

        print(
            f"🔬 Disease: {disease}"
        )

        print(
            f"📊 Confidence: "
            f"{confidence:.4f}"
        )

        print(
            f"📌 Status: {status}"
        )

        # ----------------------------------------------------
        # CONFIDENCE CHECK
        # ----------------------------------------------------

        if status == "uncertain":

            response_twiml.message(
                with_welcome(
                    "⚠️ The image is not clear enough "
                    "for a reliable diagnosis.\n\n"
                    "Please send a clearer photo of the "
                    "affected leaf."
                )
            )

            return Response(
                content=str(response_twiml),
                media_type="application/xml"
            )

        # ----------------------------------------------------
        # LOCATION FALLBACK
        # ----------------------------------------------------

        latitude = session.get(
            "latitude"
        )

        longitude = session.get(
            "longitude"
        )

        if latitude is None or longitude is None:

            # Hyderabad fallback
            # Keeps the demo functional if farmer
            # hasn't supplied a district yet.

            latitude = 17.3850
            longitude = 78.4867

            print(
                "📍 No location supplied. "
                "Using Hyderabad fallback."
            )

        else:

            print(
                f"📍 Location: "
                f"{latitude}, {longitude}"
            )

        # ----------------------------------------------------
        # CROP STAGE
        # ----------------------------------------------------

        sowing_date = session.get(
            "sowing_date"
        )

        stage_info = None

        if sowing_date:

            stage_info, stage_error = (
                get_crop_stage(
                    crop,
                    sowing_date
                )
            )

            if stage_info:

                print(
                    f"🌱 Crop stage: "
                    f"{stage_info['stage_name']}"
                )

                print(
                    f"📅 Days since sowing: "
                    f"{stage_info['days_since_sowing']}"
                )

            else:

                print(
                    f"⚠️ Crop stage error: "
                    f"{stage_error}"
                )

        else:

            print(
                "⚠️ No sowing date provided"
            )

        # ----------------------------------------------------
        # FALLBACK STAGE
        # ----------------------------------------------------

        if not stage_info:

            stage_info = {
                "stage_name": "unknown",
                "stage_description": (
                    "Crop stage unavailable"
                ),
                "days_since_sowing": 0,
                "susceptibility": "Unknown",
                "is_critical": False,
                "progress_percentage": 0,
                "days_until_harvest": 0,
            }

        crop_stage = stage_info.get(
            "stage_name",
            "unknown"
        )

        # ----------------------------------------------------
        # WEATHER
        # ----------------------------------------------------

        weather_context = None

        weather_context, weather_error = (
            weather_client_instance
            .get_weather_context(
                latitude,
                longitude
            )
        )

        if weather_context:

            weather_risk = assess_weather_risk(
                weather_context
            )

            weather_summary = (
                weather_client_instance
                .get_weather_summary(
                    weather_context
                )
            )

            weather_risk["summary"] = (
                weather_summary
            )

            print(
                f"🌤️ Weather risk: "
                f"{weather_risk['risk_level']}"
            )

        else:

            print(
                f"⚠️ Weather error: "
                f"{weather_error}"
            )

            weather_risk = {
                "risk_level": "low",
                "risk_score": 0,
                "risk_factors": [],
                "summary": (
                    "Weather data unavailable"
                )
            }

        # ----------------------------------------------------
        # ADVISORY ENGINE
        # ----------------------------------------------------

        advisory, advisory_error = get_advisory(
            disease=disease,
            confidence=confidence,
            crop=crop,
            crop_stage=crop_stage,
            weather_risk=weather_risk,
            stage_info=stage_info
        )

        if advisory is None:

            print(
                f"⚠️ Advisory unavailable: "
                f"{advisory_error}"
            )

            response_twiml.message(
                with_welcome(
                    "⚠️ Disease identified, but an "
                    "advisory is not available for "
                    "this disease yet.\n\n"
                    f"Disease: {disease}\n"
                    f"Confidence: "
                    f"{confidence * 100:.1f}%"
                )
            )

            return Response(
                content=str(response_twiml),
                media_type="application/xml"
            )

        print(
            "✅ Advisory generated"
        )

        # ----------------------------------------------------
        # ENGLISH RESPONSE
        # ----------------------------------------------------

        en_response = format_english_response(
            disease=disease,
            confidence=confidence,
            stage_info=stage_info,
            weather_risk=weather_risk,
            advisory=advisory
        )

        # ----------------------------------------------------
        # TELUGU RESPONSE
        # ----------------------------------------------------

        te_response = format_telugu_response(
            disease=disease,
            confidence=confidence,
            stage_info=stage_info,
            weather_risk=weather_risk,
            advisory=advisory
        )

        # ----------------------------------------------------
        # SEND TEXT RESPONSE
        # ----------------------------------------------------

        final_message = (
            f"{en_response}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"{te_response}"
        )

        response_twiml.message(
            with_welcome(final_message)
        )

        # ----------------------------------------------------
        # TELUGU TTS
        # ----------------------------------------------------

        try:

            voice_text = te_response

            audio_filename = (
                generate_telugu_audio(
                    voice_text
                )
            )

            public_base_url = (
                settings.PUBLIC_BASE_URL
                .rstrip("/")
            )

            audio_url = (
                f"{public_base_url}"
                f"/audio/"
                f"{audio_filename}"
            )

            audio_message = (
                response_twiml.message()
            )

            audio_message.media(
                audio_url
            )

            print(
                f"🎧 Telugu audio generated: "
                f"{audio_filename}"
            )

            print(
                f"🔗 Audio URL: "
                f"{audio_url}"
            )

        except Exception as voice_error:

            print(
                f"⚠️ Telugu TTS failed: "
                f"{voice_error}"
            )

            traceback.print_exc()

        # ----------------------------------------------------
        # RETURN TWILIO RESPONSE
        # ----------------------------------------------------

        return Response(
            content=str(response_twiml),
            media_type="application/xml"
        )

    except Exception as error:

        print(
            "\n❌ WEBHOOK ERROR:"
        )

        print(
            str(error)
        )

        traceback.print_exc()

        response_twiml.message(
            with_welcome(
                "⚠️ Something went wrong while "
                "processing your request. "
                "Please try again."
            )
        )

        return Response(
            content=str(response_twiml),
            media_type="application/xml"
        )


# ============================================================
# TEST ROUTE
# ============================================================

@router.get("/test")
async def test_webhook():

    return {
        "status": "ok",
        "message": "WhatsApp webhook router is working"
    }