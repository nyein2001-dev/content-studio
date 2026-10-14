"""The only place that names the voice, the caption limits, and the canvas."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT_IDEA = ROOT.parent / "abitinside-original-content-idea.txt"

VOICE_ID = "en-US-AndrewNeural"
TTS_PROVIDER = "edge-tts"
SPEECH_RATE = "+0%"
RATE_CHOICES = ("-10%", "-5%", "+0%", "+5%", "+10%")

W, H = 1080, 1920
FPS = 30
SAFE_X0, SAFE_X1 = 120, 960
CAPTION_FLOOR_Y = 1610
CAPTION_MAX_WORDS = 8
CAPTION_MAX_LINES = 2
CAPTION_MAX_PX = 800
TARGET_MIN_S, TARGET_MAX_S = 100.0, 135.0

LEAD_IN_S = 4 / FPS
GAP_AFTER_DEFAULT = 0.30
GAP_BEFORE_REVEAL = 0.62
GAP_BEFORE_ENDCARD = 0.45
SENTENCE_LUFS = -16.0
TARGET_SR = 48000


def require_voice(voice: str) -> None:
    """Stop the job if anything other than Andrew is requested."""
    if voice != VOICE_ID:
        raise SystemExit(
            f"refusing voice {voice!r}; the only allowed voice is {VOICE_ID} "
            f"via {TTS_PROVIDER}. No fallback."
        )
