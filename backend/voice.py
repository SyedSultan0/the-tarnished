from gtts import gTTS
from pathlib import Path


AUDIO_DIR = Path("audio")
AUDIO_DIR.mkdir(exist_ok=True)


def generate_telugu_audio(text: str) -> str:
    """
    Convert Telugu text into an MP3 audio file.

    Returns:
        Path to the generated audio file.
    """

    output_file = AUDIO_DIR / "telugu_advisory.mp3"

    tts = gTTS(
        text=text,
        lang="te",
        slow=False
    )

    tts.save(str(output_file))

    return str(output_file)