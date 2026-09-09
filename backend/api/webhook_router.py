
"""
webhook_router.py - WhatsApp Webhook Handler for THE TARNISHED
Complete fixed version with proper image handling and deterministic model inference
"""

import re
import traceback
from typing import Annotated, Optional, Dict, Any

from fastapi import APIRouter, Form, Response, UploadFile
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client

# Import our modules
from core.config import settings
from model import predict_maize
from weather import get_weather_client, assess_weather_risk
from crop_stage import get_crop_stage
from advisory import get_advisory


# ------------------------------------------------------------------
# CREATE ROUTER
# ------------------------------------------------------------------

router = APIRouter()


# ------------------------------------------------------------------
# SESSION MANAGEMENT
# ------------------------------------------------------------------

user_sessions: Dict[str, Dict[str, Any]] = {}


def get_user_session(user_id: str) -> Dict[str, Any]:
    """Get or create a user session."""

    if user_id not in user_sessions:

        user_sessions[user_id] = {
            "crop": "maize",
            "sowing_date": None,
            "location": None,
            "lat": None,
            "lon": None,
            "stage": "vegetative",
            "lang": "te",
            "last_message": None,
            "conversation_state": "idle"
        }

    return user_sessions[user_id]


def update_user_session(
    user_id: str,
    data: Dict[str, Any]
):
    """Update user session data."""

    session = get_user_session(user_id)

    session.update(data)

    user_sessions[user_id] = session


# ------------------------------------------------------------------
# TWILIO CLIENT
# ------------------------------------------------------------------

_twilio_client = None


def get_twilio_client():
    """Get or create Twilio client."""

    global _twilio_client

    if _twilio_client is None:

        _twilio_client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN
        )

    return _twilio_client


# ------------------------------------------------------------------
# WEATHER CLIENT
# ------------------------------------------------------------------

_weather_client = None


def get_weather_client_instance():
    """Get or create weather client."""

    global _weather_client

    if _weather_client is None:

        _weather_client = get_weather_client()

    return _weather_client


# ------------------------------------------------------------------
# IMAGE HANDLING FUNCTIONS
# ------------------------------------------------------------------

def download_whatsapp_image(
    media_url: str
) -> Optional[bytes]:
    """
    Download an image from Twilio WhatsApp media URL.
    """

    import requests

    try:

        print(
            f"📥 Downloading image from: "
            f"{media_url}"
        )

        response = requests.get(
            media_url,
            auth=(
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN
            ),
            timeout=settings.WHATSAPP_MEDIA_TIMEOUT
        )

        response.raise_for_status()

        print(
            f"   Downloaded: "
            f"{len(response.content)} bytes"
        )

        return response.content

    except Exception as e:

        print(
            f"❌ Error downloading image: {e}"
        )

        return None


def validate_and_prepare_image(
    image_bytes: bytes
):
    """
    Validate and prepare image for model inference.

    IMPORTANT:
    Returns a normal PIL Image.

    We intentionally DO NOT create a FastAI PILImage here.
    model.py performs deterministic preprocessing itself.
    """

    from PIL import Image
    import io

    try:

        print(
            "📸 Validating and preparing image..."
        )

        # ----------------------------------------------------------
        # OPEN IMAGE
        # ----------------------------------------------------------

        pil_image = Image.open(
            io.BytesIO(image_bytes)
        )

        print(
            f"   Original: "
            f"{pil_image.width}x{pil_image.height}, "
            f"Mode: {pil_image.mode}"
        )

        # ----------------------------------------------------------
        # LOAD IMAGE INTO MEMORY
        # ----------------------------------------------------------

        pil_image.load()

        # ----------------------------------------------------------
        # CONVERT TO RGB
        # ----------------------------------------------------------

        if pil_image.mode != "RGB":

            print(
                f"   Converting from "
                f"{pil_image.mode} to RGB"
            )

            pil_image = pil_image.convert("RGB")

        else:

            # Make an independent copy.
            # This prevents issues with closed file handles
            # or lazy PIL image data.
            pil_image = pil_image.copy()

        # ----------------------------------------------------------
        # RESIZE IF TOO LARGE
        # ----------------------------------------------------------

        max_size = 1024

        if (
            pil_image.width > max_size
            or pil_image.height > max_size
        ):

            pil_image.thumbnail(
                (
                    max_size,
                    max_size
                ),
                Image.Resampling.LANCZOS
            )

            print(
                f"   Resized to: "
                f"{pil_image.width}x"
                f"{pil_image.height}"
            )

        # ----------------------------------------------------------
        # ENSURE MINIMUM SIZE
        # ----------------------------------------------------------

        if (
            pil_image.width < 100
            or pil_image.height < 100
        ):

            print(
                f"❌ Image too small: "
                f"{pil_image.width}x"
                f"{pil_image.height}"
            )

            return None

        print(
            f"✅ Valid image: "
            f"{pil_image.width}x"
            f"{pil_image.height}, "
            f"Mode: {pil_image.mode}"
        )

        return pil_image

    except Exception as e:

        print(
            f"❌ Image validation failed: {e}"
        )

        traceback.print_exc()

        return None


# ------------------------------------------------------------------
# BILINGUAL RESPONSE
# ------------------------------------------------------------------

def generate_bilingual_response(
    en_text: str,
    te_text: str
) -> str:
    """Generate bilingual response for WhatsApp."""

    return (
        f"{en_text}\n\n"
        f"{te_text}"
    )


# ------------------------------------------------------------------
# SOWING DATE EXTRACTION
# ------------------------------------------------------------------

def extract_sowing_date(
    text: str
) -> Optional[str]:
    """
    Extract sowing date from user message.

    Supports:
        DD/MM/YYYY
        DD-MM-YYYY
        DD.MM.YYYY

    And:
        YYYY/MM/DD
        YYYY-MM-DD
        YYYY.MM.DD
    """

    patterns = [

        r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})",

        r"(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})"

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text
        )

        if match:

            groups = match.groups()

            # YYYY/MM/DD
            if len(groups[0]) == 4:

                return (
                    f"{groups[2]}/"
                    f"{groups[1]}/"
                    f"{groups[0]}"
                )

            # DD/MM/YYYY
            else:

                return (
                    f"{groups[0]}/"
                    f"{groups[1]}/"
                    f"{groups[2]}"
                )

    return None


# ------------------------------------------------------------------
# LOCATION EXTRACTION
# ------------------------------------------------------------------

def extract_location(
    text: str
) -> Optional[str]:
    """Extract location from user message."""

    telangana_districts = [

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
        "yadadri"
    ]

    text_lower = text.lower()

    for district in telangana_districts:

        if district in text_lower:

            return district.title()

    return None


# ------------------------------------------------------------------
# DISTRICT COORDINATES
# ------------------------------------------------------------------

def get_district_coordinates(
    district: str
) -> tuple:
    """Get approximate coordinates for Telangana districts."""

    coords = {

        "hyderabad": (
            17.3850,
            78.4867
        ),

        "warangal": (
            18.0000,
            79.5833
        ),

        "nizamabad": (
            18.6713,
            78.1019
        ),

        "khammam": (
            17.2473,
            80.1514
        ),

        "karimnagar": (
            18.4392,
            79.1286
        ),

        "mahabubnagar": (
            16.7422,
            77.9856
        ),

        "adilabad": (
            19.6667,
            78.5333
        ),

        "nalgonda": (
            17.0575,
            79.2672
        ),

        "sangareddy": (
            17.6220,
            78.1006
        ),

        "medak": (
            18.0417,
            78.2640
        ),

        "siddipet": (
            18.1010,
            78.8470
        ),

        "jagtial": (
            18.7954,
            78.9167
        ),

        "mancherial": (
            18.8709,
            79.4253
        ),

        "peddapalli": (
            18.6081,
            79.3764
        ),

        "kamareddy": (
            18.3200,
            78.3400
        ),

        "bhongir": (
            17.5150,
            78.8900
        ),

        "suryapet": (
            17.1406,
            79.6244
        ),

        "jangaon": (
            17.7247,
            79.1680
        ),

        "gadwal": (
            16.2357,
            77.7959
        ),

        "nagarkurnool": (
            16.4820,
            78.3250
        ),

        "vikarabad": (
            17.3380,
            77.9040
        ),

        "yadadri": (
            17.5885,
            79.0280
        )
    }

    return coords.get(
        district.lower(),
        (
            17.3850,
            78.4867
        )
    )


# ------------------------------------------------------------------
# MAIN WEBHOOK ENDPOINT
# ------------------------------------------------------------------

@router.post("/webhook")
async def whatsapp_webhook(

    From: Annotated[
        str,
        Form()
    ],

    Body: Annotated[
        Optional[str],
        Form()
    ] = None,

    NumMedia: Annotated[
        int,
        Form()
    ] = 0,

    MediaUrl0: Annotated[
        Optional[str],
        Form()
    ] = None

):
    """
    Main WhatsApp webhook handler.

    Receives messages from Twilio
    and processes them.
    """

    response_twiml = MessagingResponse()

    user_id = From

    print(
        f"\n{'=' * 50}"
    )

    print(
        f"📱 Message from: {user_id}"
    )

    print(
        f"📝 Body: {Body}"
    )

    print(
        f"📸 NumMedia: {NumMedia}"
    )

    print(
        f"{'=' * 50}"
    )

    try:

        session = get_user_session(
            user_id
        )

        # ==========================================================
        # HANDLE IMAGES
        # ==========================================================

        if NumMedia > 0 and MediaUrl0:

            print(
                f"📸 Processing image "
                f"from {user_id}"
            )

            # ------------------------------------------------------
            # DOWNLOAD IMAGE
            # ------------------------------------------------------

            image_bytes = (
                download_whatsapp_image(
                    MediaUrl0
                )
            )

            if image_bytes is None:

                message = (
                    generate_bilingual_response(

                        "❌ Could not download image. "
                        "Please try again with a clearer photo.",

                        "❌ ఫోటో డౌన్లోడ్ చేయడంలో "
                        "విఫలమైంది. దయచేసి మళ్లీ ప్రయత్నించండి."
                    )
                )

                response_twiml.message(
                    message
                )

                return Response(
                    content=str(response_twiml),
                    media_type="application/xml"
                )

            # ------------------------------------------------------
            # VALIDATE IMAGE
            # ------------------------------------------------------

            validated_image = (
                validate_and_prepare_image(
                    image_bytes
                )
            )

            if validated_image is None:

                message = (
                    generate_bilingual_response(

                        "❌ Could not process image. "
                        "Please send a clear photo "
                        "of the crop leaf.",

                        "❌ ఫోటో ప్రాసెస్ చేయడంలో "
                        "విఫలమైంది. దయచేసి స్పష్టమైన "
                        "పంట ఆకు ఫోటో పంపండి."
                    )
                )

                response_twiml.message(
                    message
                )

                return Response(
                    content=str(response_twiml),
                    media_type="application/xml"
                )

            # ======================================================
            # RUN DISEASE PREDICTION
            # ======================================================

            try:

                print(
                    "🔬 Image prepared, "
                    "running model prediction..."
                )

                # IMPORTANT:
                #
                # Pass the NORMAL PIL image directly.
                #
                # DO NOT use:
                #
                # FastAIPIL.create(validated_image)
                #
                # The model.py inference function now performs
                # deterministic preprocessing itself.
                #
                # This avoids the FastAI training-time random
                # augmentation / crop_pad path that was causing
                # the PIL AssertionError.

                result = predict_maize(
                    validated_image
                )

                disease = result["disease"]

                confidence = result["confidence"]

                status = result["status"]

                print(
                    f"🔬 Prediction: {disease} "
                    f"(confidence: {confidence:.2f}, "
                    f"status: {status})"
                )

                # ==================================================
                # HANDLE UNCERTAIN PREDICTION
                # ==================================================

                if status == "uncertain":

                    message = (
                        generate_bilingual_response(

                            (
                                "⚠️ I'm not confident "
                                "about this image "
                                f"(confidence: "
                                f"{confidence:.1%}).\n\n"

                                "📸 Please send a clearer "
                                "photo with:\n"

                                "• Better lighting\n"

                                "• Close-up of the "
                                "affected leaf\n"

                                "• Single leaf, not "
                                "multiple leaves\n\n"

                                "If the problem continues, "
                                "consult a local "
                                "agricultural officer."
                            ),

                            (
                                "⚠️ ఈ ఫోటో గురించి నాకు "
                                "ఖచ్చితంగా తెలియదు "
                                f"(నమ్మకం: "
                                f"{confidence:.1%}).\n\n"

                                "📸 దయచేసి స్పష్టమైన "
                                "ఫోటో పంపండి:\n"

                                "• మంచి వెలుతురు\n"

                                "• ప్రభావిత ఆకు దగ్గరగా\n"

                                "• ఒకే ఆకు, బహుళ "
                                "ఆకులు కాదు\n\n"

                                "సమస్య కొనసాగితే, "
                                "స్థానిక వ్యవసాయ "
                                "అధికారిని సంప్రదించండి."
                            )
                        )
                    )

                    response_twiml.message(
                        message
                    )

                    return Response(
                        content=str(response_twiml),
                        media_type="application/xml"
                    )

                # ==================================================
                # GET WEATHER DATA
                # ==================================================

                if (
                    session.get("lat") is not None
                    and
                    session.get("lon") is not None
                ):

                    lat = session["lat"]

                    lon = session["lon"]

                else:

                    # Default Telangana fallback
                    lat = 17.3850
                    lon = 78.4867

                weather_client = (
                    get_weather_client_instance()
                )

                (
                    weather_context,
                    weather_error
                ) = (
                    weather_client.get_weather_context(
                        lat,
                        lon
                    )
                )

                if weather_context:

                    weather_risk = (
                        assess_weather_risk(
                            weather_context
                        )
                    )

                    weather_summary = (
                        weather_client.get_weather_summary(
                            weather_context
                        )
                    )

                else:

                    weather_risk = {
                        "risk_level": "moderate",
                        "summary": (
                            "Weather data unavailable"
                        )
                    }

                    weather_summary = (
                        "Weather data unavailable"
                    )

                # ==================================================
                # GET CROP STAGE
                # ==================================================

                crop = session.get(
                    "crop",
                    "maize"
                )

                sowing_date = session.get(
                    "sowing_date"
                )

                if sowing_date:

                    (
                        stage_info,
                        stage_error
                    ) = get_crop_stage(
                        crop,
                        sowing_date
                    )

                    if stage_info:

                        crop_stage = (
                            stage_info["stage_name"]
                        )

                    else:

                        crop_stage = (
                            "vegetative"
                        )

                        stage_info = {
                            "susceptibility": "Medium"
                        }

                else:

                    crop_stage = (
                        "vegetative"
                    )

                    stage_info = {
                        "susceptibility": "Medium"
                    }

                # ==================================================
                # GENERATE ADVISORY
                # ==================================================

                (
                    advisory,
                    advisory_error
                ) = get_advisory(

                    disease=disease,

                    confidence=confidence,

                    crop=crop,

                    crop_stage=crop_stage,

                    weather_risk=weather_risk,

                    stage_info=stage_info
                )

                if advisory_error:

                    message = (
                        generate_bilingual_response(

                            (
                                f"🔬 Disease: "
                                f"{disease}\n"

                                f"Confidence: "
                                f"{confidence:.1%}\n\n"

                                "⚠️ Advisory "
                                "generation failed: "

                                f"{advisory_error}\n\n"

                                "Please consult a local "
                                "agricultural officer."
                            ),

                            (
                                f"🔬 వ్యాధి: "
                                f"{disease}\n"

                                f"నమ్మకం: "
                                f"{confidence:.1%}\n\n"

                                "⚠️ సలహా రూపొందించడంలో "
                                "విఫలమైంది: "

                                f"{advisory_error}\n\n"

                                "దయచేసి స్థానిక "
                                "వ్యవసాయ అధికారిని "
                                "సంప్రదించండి."
                            )
                        )
                    )

                    response_twiml.message(
                        message
                    )

                    return Response(
                        content=str(response_twiml),
                        media_type="application/xml"
                    )

                # ==================================================
                # FORMAT ENGLISH RESPONSE
                # ==================================================

                en_response = (
                    "🌾 THE TARNISHED - "
                    "Crop Advisory\n"
                )

                en_response += (
                    f"{'=' * 30}\n"
                )

                en_response += (
                    f"🔬 Disease: "
                    f"{advisory['disease']}\n"
                )

                en_response += (
                    f"📊 Confidence: "
                    f"{advisory['disease_confidence']:.1%}\n"
                )

                en_response += (
                    f"🌱 Stage: "
                    f"{advisory['crop_stage']}\n"
                )

                en_response += (
                    f"🌤️ Weather: "
                    f"{advisory['weather_risk_level']} "
                    f"risk\n\n"
                )

                en_response += (
                    "📝 RECOMMENDATION:\n"
                )

                en_response += (
                    f"• Action: "
                    f"{advisory['action']}\n"
                )

                en_response += (
                    f"• Product: "
                    f"{advisory['product']}\n"
                )

                en_response += (
                    f"• Dosage: "
                    f"{advisory['dosage']}\n"
                )

                en_response += (
                    f"• Timing: "
                    f"{advisory['timing']}\n\n"
                )

                # --------------------------------------------------
                # SAFETY PRECAUTIONS
                # --------------------------------------------------

                if advisory[
                    "safety_precautions"
                ]:

                    en_response += (
                        "⚠️ Safety:\n"
                    )

                    for safety in advisory[
                        "safety_precautions"
                    ][:3]:

                        en_response += (
                            f"• {safety}\n"
                        )

                    en_response += "\n"

                en_response += (
                    f"📈 Expected: "
                    f"{advisory['expected_result']}\n"
                )

                en_response += (
                    f"⏰ Urgency: "
                    f"{advisory['urgency']}"
                )

                # ==================================================
                # TELUGU RESPONSE
                # ==================================================

                te_response = (
                    "🌾 ది టార్నిష్డ్ - "
                    "పంట సలహా\n"
                )

                te_response += (
                    f"{'=' * 30}\n"
                )

                te_response += (
                    f"🔬 వ్యాధి: "
                    f"{advisory['disease']}\n"
                )

                te_response += (
                    f"📊 నమ్మకం: "
                    f"{advisory['disease_confidence']:.1%}\n"
                )

                te_response += (
                    f"🌱 దశ: "
                    f"{advisory['crop_stage']}\n"
                )

                te_response += (
                    f"🌤️ వాతావరణం: "
                    f"{advisory['weather_risk_level']} "
                    f"ప్రమాదం\n\n"
                )

                te_response += (
                    "📝 సిఫార్సు:\n"
                )

                te_response += (
                    f"• చర్య: "
                    f"{advisory['action']}\n"
                )

                te_response += (
                    f"• ఉత్పత్తి: "
                    f"{advisory['product']}\n"
                )

                te_response += (
                    f"• మోతాదు: "
                    f"{advisory['dosage']}\n"
                )

                te_response += (
                    f"• సమయం: "
                    f"{advisory['timing']}\n\n"
                )

                # --------------------------------------------------
                # TELUGU SAFETY
                # --------------------------------------------------

                if advisory[
                    "safety_precautions"
                ]:

                    te_response += (
                        "⚠️ భద్రత:\n"
                    )

                    for safety in advisory[
                        "safety_precautions"
                    ][:3]:

                        te_response += (
                            f"• {safety}\n"
                        )

                    te_response += "\n"

                te_response += (
                    f"📈 ఆశించిన ఫలితం: "
                    f"{advisory['expected_result']}\n"
                )

                te_response += (
                    f"⏰ అత్యవసరం: "
                    f"{advisory['urgency']}"
                )

                # ==================================================
                # FINAL WHATSAPP RESPONSE
                # ==================================================

                final_message = (
                    f"{en_response}\n\n"
                    f"---\n\n"
                    f"{te_response}"
                )

                final_message += (
                    "\n\n"
                    "🎧 Voice advisory in Telugu "
                    "coming soon!"
                )

                response_twiml.message(
                    final_message
                )

                return Response(
                    content=str(response_twiml),
                    media_type="application/xml"
                )

            # ======================================================
            # IMAGE PREDICTION ERROR
            # ======================================================

            except Exception as e:

                print(
                    f"❌ Prediction error: {e}"
                )

                traceback.print_exc()

                message = (
                    generate_bilingual_response(

                        (
                            "❌ Error processing image: "
                            f"{str(e)[:100]}\n\n"
                            "Please try again with "
                            "a clearer photo."
                        ),

                        (
                            "❌ ఫోటో ప్రాసెస్ చేయడంలో "
                            "లోపం\n\n"
                            "దయచేసి మళ్లీ ప్రయత్నించండి."
                        )
                    )
                )

                response_twiml.message(
                    message
                )

                return Response(
                    content=str(response_twiml),
                    media_type="application/xml"
                )

        # ==========================================================
        # HANDLE TEXT COMMANDS
        # ==========================================================

        if Body:

            body_lower = (
                Body.lower().strip()
            )

            # ------------------------------------------------------
            # JOIN
            # ------------------------------------------------------

            if "join" in body_lower:

                message = (
                    generate_bilingual_response(

                        (
                            "✅ Connected to "
                            "THE TARNISHED "
                            "Crop Advisory!\n\n"

                            "📸 Send a photo of "
                            "your crop leaf\n"

                            "📍 Tell me your district "
                            "(e.g., Hyderabad)\n"

                            "📅 Tell me your sowing date "
                            "(e.g., 15/06/2026)\n\n"

                            "🌾 Supported crops: "
                            "Maize (first), Cotton, "
                            "Paddy, Chilli\n\n"

                            "💡 Tip: Send 'Help' "
                            "for more info"
                        ),

                        (
                            "✅ ది టార్నిష్డ్ పంట "
                            "సలహా వ్యవస్థకు "
                            "కనెక్ట్ అయ్యారు!\n\n"

                            "📸 మీ పంట ఆకు ఫోటోను "
                            "పంపండి\n"

                            "📍 మీ జిల్లా చెప్పండి "
                            "(ఉదా: హైదరాబాద్)\n"

                            "📅 మీ విత్తన తేదీ చెప్పండి "
                            "(ఉదా: 15/06/2026)\n\n"

                            "🌾 మద్దతు ఉన్న పంటలు: "
                            "మొక్కజొన్న (మొదట), "
                            "పత్తి, వరి, మిరప"
                        )
                    )
                )

                response_twiml.message(
                    message
                )

                return Response(
                    content=str(response_twiml),
                    media_type="application/xml"
                )

            # ------------------------------------------------------
            # HELP / GREETING
            # ------------------------------------------------------

            if body_lower in [
                "help",
                "hi",
                "hello",
                "నమస్కారం",
                "హాయ్"
            ]:

                message = (
                    generate_bilingual_response(

                        (
                            "🌾 THE TARNISHED - Help\n\n"

                            "📸 Send a photo of your "
                            "crop leaf for disease "
                            "diagnosis\n"

                            "📍 Send your district "
                            "name for weather data "
                            "(e.g., Hyderabad)\n"

                            "📅 Send your sowing date "
                            "(e.g., 15/06/2026)\n\n"

                            "Supported crops: "
                            "Maize, Cotton, Paddy, Chilli\n\n"

                            "Example:\n"

                            "1. 'Hyderabad' - "
                            "sets location\n"

                            "2. '15/06/2026' - "
                            "sets sowing date\n"

                            "3. Send photo - "
                            "gets diagnosis"
                        ),

                        (
                            "🌾 ది టార్నిష్డ్ - సహాయం\n\n"

                            "📸 వ్యాధి నిర్ధారణ కోసం "
                            "మీ పంట ఆకు ఫోటోను పంపండి\n"

                            "📍 వాతావరణ డేటా కోసం "
                            "మీ జిల్లా పంపండి "
                            "(ఉదా: హైదరాబాద్)\n"

                            "📅 మీ విత్తన తేదీ పంపండి "
                            "(ఉదా: 15/06/2026)\n\n"

                            "మద్దతు ఉన్న పంటలు: "
                            "మొక్కజొన్న, పత్తి, వరి, మిరప"
                        )
                    )
                )

                response_twiml.message(
                    message
                )

                return Response(
                    content=str(response_twiml),
                    media_type="application/xml"
                )

            # ------------------------------------------------------
            # SOWING DATE
            # ------------------------------------------------------

            sowing_date = (
                extract_sowing_date(
                    Body
                )
            )

            if sowing_date:

                update_user_session(
                    user_id,
                    {
                        "sowing_date":
                            sowing_date
                    }
                )

                message = (
                    generate_bilingual_response(

                        (
                            "✅ Sowing date recorded: "
                            f"{sowing_date}\n\n"

                            "📸 Now send a photo "
                            "of your crop leaf "
                            "for diagnosis.\n"

                            "📍 Or tell me your "
                            "district for weather data."
                        ),

                        (
                            "✅ విత్తన తేదీ నమోదు "
                            "చేయబడింది: "
                            f"{sowing_date}\n\n"

                            "📸 ఇప్పుడు మీ పంట "
                            "ఆకు ఫోటోను పంపండి.\n"

                            "📍 లేదా వాతావరణ డేటా "
                            "కోసం మీ జిల్లా చెప్పండి."
                        )
                    )
                )

                response_twiml.message(
                    message
                )

                return Response(
                    content=str(response_twiml),
                    media_type="application/xml"
                )

            # ------------------------------------------------------
            # LOCATION
            # ------------------------------------------------------

            location = (
                extract_location(
                    Body
                )
            )

            if location:

                lat, lon = (
                    get_district_coordinates(
                        location
                    )
                )

                update_user_session(

                    user_id,

                    {
                        "location": location,
                        "lat": lat,
                        "lon": lon
                    }
                )

                message = (
                    generate_bilingual_response(

                        (
                            "✅ Location set to: "
                            f"{location}\n\n"

                            "📸 Now send a photo "
                            "of your crop leaf "
                            "for diagnosis.\n"

                            "📅 Or tell me your "
                            "sowing date."
                        ),

                        (
                            "✅ ప్రాంతం నమోదు "
                            "చేయబడింది: "
                            f"{location}\n\n"

                            "📸 ఇప్పుడు మీ పంట "
                            "ఆకు ఫోటోను పంపండి.\n"

                            "📅 లేదా మీ విత్తన "
                            "తేదీ చెప్పండి."
                        )
                    )
                )

                response_twiml.message(
                    message
                )

                return Response(
                    content=str(response_twiml),
                    media_type="application/xml"
                )

            # ------------------------------------------------------
            # CROP COMMAND
            # ------------------------------------------------------

            crop_match = re.search(
                r"crop\s*[:=]\s*(\w+)",
                body_lower
            )

            if crop_match:

                crop = (
                    crop_match.group(1)
                )

                if crop in [
                    "maize",
                    "cotton",
                    "paddy",
                    "chilli"
                ]:

                    update_user_session(
                        user_id,
                        {
                            "crop": crop
                        }
                    )

                    message = (
                        generate_bilingual_response(

                            (
                                f"✅ Crop set to: "
                                f"{crop}\n\n"

                                f"📸 Now send a photo "
                                f"of your {crop} leaf."
                            ),

                            (
                                f"✅ పంట నమోదు "
                                f"చేయబడింది: {crop}\n\n"

                                f"📸 ఇప్పుడు మీ {crop} "
                                f"ఆకు ఫోటోను పంపండి."
                            )
                        )
                    )

                    response_twiml.message(
                        message
                    )

                    return Response(
                        content=str(response_twiml),
                        media_type="application/xml"
                    )

            # ------------------------------------------------------
            # UNKNOWN COMMAND
            # ------------------------------------------------------

            message = (
                generate_bilingual_response(

                    (
                        "🌾 I didn't understand that.\n\n"

                        "📸 Send a photo of your "
                        "crop leaf for diagnosis\n"

                        "📍 Send your district name "
                        "(e.g., Hyderabad)\n"

                        "📅 Send your sowing date "
                        "(e.g., 15/06/2026)\n\n"

                        "💡 Send 'Help' for more info"
                    ),

                    (
                        "🌾 నేను అర్థం చేసుకోలేదు.\n\n"

                        "📸 వ్యాధి నిర్ధారణ కోసం "
                        "పంట ఆకు ఫోటోను పంపండి\n"

                        "📍 మీ జిల్లా పేరు పంపండి "
                        "(ఉదా: హైదరాబాద్)\n"

                        "📅 మీ విత్తన తేదీ పంపండి "
                        "(ఉదా: 15/06/2026)\n\n"

                        "💡 'Help' పంపండి "
                        "మరింత సమాచారం కోసం"
                    )
                )
            )

            response_twiml.message(
                message
            )

            return Response(
                content=str(response_twiml),
                media_type="application/xml"
            )

        # ==========================================================
        # DEFAULT WELCOME MESSAGE
        # ==========================================================

        message = (
            generate_bilingual_response(

                (
                    "🌾 Welcome to "
                    "THE TARNISHED!\n\n"

                    "📸 Send a photo of "
                    "your crop leaf\n"

                    "📍 Send your district name\n"

                    "📅 Send your sowing date\n\n"

                    "💡 Send 'Help' for more info"
                ),

                (
                    "🌾 ది టార్నిష్డ్ కి "
                    "స్వాగతం!\n\n"

                    "📸 మీ పంట ఆకు "
                    "ఫోటోను పంపండి\n"

                    "📍 మీ జిల్లా పేరు "
                    "పంపండి\n"

                    "📅 మీ విత్తన తేదీ "
                    "పంపండి\n\n"

                    "💡 'Help' పంపండి "
                    "మరింత సమాచారం కోసం"
                )
            )
        )

        response_twiml.message(
            message
        )

        return Response(
            content=str(response_twiml),
            media_type="application/xml"
        )

    # ==============================================================
    # WEBHOOK ERROR HANDLER
    # ==============================================================

    except Exception as e:

        print(
            f"❌ Webhook error: {e}"
        )

        traceback.print_exc()

        message = (
            generate_bilingual_response(

                (
                    f"❌ An error occurred: "
                    f"{str(e)[:100]}\n\n"
                    "Please try again later."
                ),

                (
                    "❌ లోపం సంభవించింది\n\n"
                    "దయచేసి తర్వాత మళ్లీ ప్రయత్నించండి."
                )
            )
        )

        response_twiml.message(
            message
        )

        return Response(
            content=str(response_twiml),
            media_type="application/xml"
        )


# ------------------------------------------------------------------
# TEST ENDPOINT
# ------------------------------------------------------------------

@router.get("/test")
async def test_webhook():
    """Test endpoint for webhook status."""

    return {

        "status": "ok",

        "message":
            "🌾 THE TARNISHED WhatsApp "
            "webhook is active!",

        "twilio_configured":
            bool(
                settings.TWILIO_ACCOUNT_SID
            ),

        "crops_supported": [
            "maize",
            "cotton",
            "paddy",
            "chilli"
        ]
    }


# ------------------------------------------------------------------
# TEST IMAGE ENDPOINT
# ------------------------------------------------------------------

@router.post("/test-image")
async def test_image_upload(
    file: UploadFile
):
    """
    Test endpoint for image upload.

    Used for debugging the disease model
    without going through WhatsApp/Twilio.
    """

    try:

        # ----------------------------------------------------------
        # READ UPLOADED FILE
        # ----------------------------------------------------------

        contents = await file.read()

        if not contents:

            return {
                "status": "error",
                "error": "Uploaded file is empty"
            }

        # ----------------------------------------------------------
        # VALIDATE IMAGE USING SAME PIPELINE
        # ----------------------------------------------------------

        image = (
            validate_and_prepare_image(
                contents
            )
        )

        if image is None:

            return {
                "status": "error",
                "error": (
                    "Could not validate image"
                )
            }

        # ----------------------------------------------------------
        # RUN MODEL
        # ----------------------------------------------------------

        print(
            "🔬 Running test-image prediction..."
        )

        # IMPORTANT:
        # Pass normal PIL image directly.
        #
        # DO NOT use FastAIPIL.create().

        result = predict_maize(
            image
        )

        # ----------------------------------------------------------
        # RETURN RESULT
        # ----------------------------------------------------------

        return {

            "status": "success",

            "prediction": result

        }

    except Exception as e:

        print(
            f"❌ Test image error: {e}"
        )

        traceback.print_exc()

        return {

            "status": "error",

            "error": str(e)

        }
