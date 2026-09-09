from gtts import gTTS
from pathlib import Path
from uuid import uuid4


BASE_DIR = Path(__file__).resolve().parent.parent
AUDIO_DIR = BASE_DIR / "audio"

AUDIO_DIR.mkdir(exist_ok=True)


def generate_telugu_audio(text: str) -> str:
    filename = f"advisory_{uuid4().hex}.mp3"
    output_file = AUDIO_DIR / filename

    tts = gTTS(
        text=text,
        lang="te",
        slow=False
    )

    tts.save(str(output_file))

    return filename