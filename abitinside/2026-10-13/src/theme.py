#!/usr/bin/env python3
"""
A Bit Inside - the visual system, locked to numbers.

Every constant here was measured from face-id-dots.mp4 (576x1024) with
src/measure_reference.py and scaled by exactly 1080/576 = 1.875. The reference is
never upscaled into the render; only its measurements are scaled.

Measured (in 1080x1920 space, from the reference):
    wordmark band          y  232.5 .. 264.4   centre 250   (scale 1.875)
    headline line 1 cap    y  363.8 .. 406.9   -> cap height ~45px
    headline line 2 cap    y  436.9 .. 493.1   (includes a comma descender)
    headline line pitch    73.1
    underline              y  511.9 .. 515.6   x 480..598  (w 120)  centre x 539
    captions               y 1470.0 .. 1541.2  centre 1505  centre x 539
    background             #030815 top  #040712 bottom corners
    accents                cyan #2ABFEA  yellow #EABF40  coral #EA5555
                           green #15BF80  deep blue #2A5580
Accent hexes are brightened ~6% over the measured values because the measurement
was taken after yuv420p+H.264 subsampling had already crushed the darkest levels.
"""
from __future__ import annotations

from pathlib import Path

ABIT = Path(__file__).resolve().parent.parent.parent
FONTS_DIR = ABIT / "assets" / "fonts"

# ----------------------------------------------------------------- canvas
W, H = 1080, 1920
FPS = 30
SCALE_FROM_REFERENCE = W / 576.0          # 1.875 exactly

# ----------------------------------------------------------------- palette
BG_TOP = "#060D20"        # measured #030815, lifted for the 8-bit round trip
BG_BOTTOM = "#020510"     # measured #040712 / #020714
BG_CORNER = "#01030B"
GLOW = "#0B2350"          # soft radial glow behind the illustration
GLOW_ALPHA = 0.55

INK = "#FFFFFF"           # pure white body text
INK_DIM = "#C3CEE0"       # secondary text, still 7:1+ on the background
INK_FAINT = "#8FA0BC"

CYAN = "#2FC6F2"          # the subject / the answer
CYAN_DEEP = "#2AAAD4"
YELLOW = "#F0C64A"        # numbers / emphasis
CORAL = "#F06060"         # problem / danger / myth
GREEN = "#22CC8C"         # success / safe
VIOLET = "#6B6BF0"
ORANGE = "#F5852A"

STAR = "#9FC4FF"

STROKE = 3                # minimum line weight (spec: >= 2)
STROKE_THIN = 2

# ----------------------------------------------------------------- type
FONT_BOLD = str(FONTS_DIR / "Poppins-Bold.ttf")
FONT_SEMI = str(FONTS_DIR / "Poppins-SemiBold.ttf")
FONT_REG = str(FONTS_DIR / "Poppins-Regular.ttf")
FONT_MONO = str(FONTS_DIR / "JetBrainsMono.ttf")

SIZE_WORDMARK = 30
SIZE_HEADLINE = 66        # measured cap height 45 / 0.70 Poppins cap ratio
SIZE_HEADLINE_SUB = 40
SIZE_PILL = 40
SIZE_LABEL = 36
SIZE_CAPTION = 72         # measured caption band 71px ascender..descender
SIZE_BIG_NUM = 128
SIZE_MIN = 34             # hard floor from the spec, checked by qa.py

# ----------------------------------------------------------------- geometry
CENTER_X = 540.0

SAFE_X0, SAFE_X1 = 120, 960
SAFE_W = SAFE_X1 - SAFE_X0                  # 840

WORDMARK_Y = 250.0
WORDMARK_BAR_W = 9
WORDMARK_BAR_H = 46
WORDMARK_GAP = 16

HEADLINE_TOP = 364.0                       # cap top of line 1 (measured)
HEADLINE_LINE_PITCH = 73.0                 # measured
HEADLINE_MAX_LINES = 2
HEADLINE_MAX_WORDS_PER_LINE = 4
HEADLINE_MAX_WORDS_TOTAL = 8

UNDERLINE_Y = 512.0
UNDERLINE_W = 120.0                        # measured
UNDERLINE_H = 5.0

ILLUSTRATION_TOP = 560.0
ILLUSTRATION_BOTTOM = 1420.0               # qa.py: illustration ink stays above this
ILLUSTRATION_X0, ILLUSTRATION_X1 = 120, 960

CAPTION_CENTER_Y = 1505.0                  # measured 1505.5
CAPTION_LINE_PITCH = 80.0
CAPTION_MAX_LINES = 2
CAPTION_FLOOR_Y = 1610.0                   # nothing below this

# ----------------------------------------------------------------- motion
HEADLINE_IN_FRAMES = 12                    # slide-up + fade, ease-out cubic
HEADLINE_OUT_FRAMES = 8
CAPTION_IN_FRAMES = 5
PATTERN_INTERRUPT_MIN_S = 2.0
PATTERN_INTERRUPT_MAX_S = 4.0
SHAKE_MAX_PX = 7
PAYOFF_HOLD_S = 1.5
ENDCARD_MAX_S = 1.5

# ----------------------------------------------------------------- easing
def clamp01(t: float) -> float:
    return 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)


def ease_out_cubic(t: float) -> float:
    t = clamp01(t)
    return 1.0 - (1.0 - t) ** 3


def ease_in_out_cubic(t: float) -> float:
    t = clamp01(t)
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out_back(t: float, overshoot: float = 1.70158) -> float:
    """Back-overshoot, only for pops (labels, counters). Never for data draws."""
    t = clamp01(t)
    c3 = overshoot + 1.0
    return 1 + c3 * (t - 1) ** 3 + overshoot * (t - 1) ** 2


def ease_linear(t: float) -> float:
    return clamp01(t)


def progress(frame: float, start: float, end: float) -> float:
    if end <= start:
        return 1.0
    return clamp01((frame - start) / (end - start))


# ----------------------------------------------------------------- palette helpers
def hex_to_rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def with_alpha(hex_colour: str, alpha: float) -> tuple[float, float, float, float]:
    r, g, b = hex_to_rgb(hex_colour)
    return (r, g, b, alpha)


# Semantic roles, so scenes never reach for raw hex directly.
SUBJECT = CYAN            # the thing being explained
NUMBER = YELLOW           # numbers and emphasis
PROBLEM = CORAL           # danger, myth, wrong
SUCCESS = GREEN           # correct, safe, fixed


def relative_luminance(hex_colour: str) -> float:
    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = hex_to_rgb(hex_colour)
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast_ratio(fg: str, bg: str) -> float:
    a, b = relative_luminance(fg), relative_luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


# Background the text actually sits on (worst case: the glow centre).
TEXT_BACKDROP = "#060D20"