"""
config.py - Configuration for THE TARNISHED
"""

import os
from pydantic_settings import BaseSettings
from pathlib import Path

# Base directory (backend folder)
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    
    # ------------------------------------------------------------------
    # TWILIO WHATSAPP CONFIGURATION
    # ------------------------------------------------------------------
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_NUMBER: str = "whatsapp:+17372508034"  # ← ADD THIS
    TWILIO_WHATSAPP_SANDBOX_CODE: str = "join twilio-trial"  # ← ADD THIS
    
    # ------------------------------------------------------------------
    # TTS CONFIGURATION (Optional)
    # ------------------------------------------------------------------
    TTS_API_KEY: str = ""
    TTS_VOICE: str = "te-IN"  # Telugu (India)
    
    # ------------------------------------------------------------------
    # MODEL PATHS
    # ------------------------------------------------------------------
    MODEL_PATH: str = str(PROJECT_ROOT / "models" / "maize_classifier.pkl")
    
    # ------------------------------------------------------------------
    # API CONFIGURATION
    # ------------------------------------------------------------------
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = False
    
    # ------------------------------------------------------------------
    # CONFIDENCE THRESHOLDS
    # ------------------------------------------------------------------
    HIGH_CONFIDENCE_THRESHOLD: float = 0.70
    UNCERTAIN_THRESHOLD: float = 0.50
    
    # ------------------------------------------------------------------
    # WHATSAPP CONFIGURATION
    # ------------------------------------------------------------------
    WHATSAPP_MEDIA_TIMEOUT: int = 30
    MAX_IMAGE_SIZE_MB: int = 5
    
    # ------------------------------------------------------------------
    # CROP CONFIGURATION
    # ------------------------------------------------------------------
    DEFAULT_CROP: str = "maize"
    SUPPORTED_CROPS: list = ["maize", "cotton", "paddy", "chilli"]
    
    class Config:
        env_file = os.path.join(BASE_DIR, '.env')
        env_file_encoding = 'utf-8'
        case_sensitive = True
        extra = "ignore"
    
    def validate_paths(self) -> bool:
        """Validate that required paths exist"""
        model_path = Path(self.MODEL_PATH)
        if not model_path.exists():
            print(f"⚠️ Warning: Model file not found at: {model_path}")
            return False
        return True


# Create global settings instance
settings = Settings()

# Print configuration on load
if settings.DEBUG:
    print("🔧 THE TARNISHED Configuration:")
    print(f"   Model Path: {settings.MODEL_PATH}")
    print(f"   WhatsApp Number: {settings.TWILIO_WHATSAPP_NUMBER}")
    print(f"   Supported Crops: {', '.join(settings.SUPPORTED_CROPS)}")
    print(f"   Confidence Threshold: {settings.HIGH_CONFIDENCE_THRESHOLD}")