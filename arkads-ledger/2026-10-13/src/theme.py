"""Arkad's Ledger - the visual system.

Every colour, size and safe-zone number for this channel lives here. Nothing in
`scenes.py`, `geo/` or `thumbnail.py` hard-codes a literal.

Palette values were measured from the reference render
(`v4-dollar-loop.mp4` and its thumbnail): the dominant quantised colours in the
thumbnail are #001830 / #000018 / #000030 for the navy ground, #F0F0D8 and
#FCF7E0 for the ivory type and #D8A818 for the brand gold. Those were lifted a
few levels because the measurement was taken after 8-bit yuv420p subsampling.
"""
from __future__ import annotations

import sys
from pathlib import Path

CHANNEL = Path(__file__).resolve().parents[2]     # src/ -> 2026-10-13/ -> arkads-ledger/
ROOT = CHANNEL.parents[0]                        # the studio repo root
sys.path.insert(0, str(ROOT))

FONTS_DIR = CHANNEL / "assets" / "fonts"

W, H, FPS = 1080, 1920, 30

# ---------------------------------------------------------------- palette
BG_TOP = "#05112B"
BG_BOTTOM = "#020A1C"
BG_CORNER = "#01050E"
GLOW = "#0B2350"
GLOW_ALPHA = 0.50
RAY = "#3E6AB0"
GRID = "#2A4A80"
DUST = "#E8A628"

IVORY = "#F2EBD8"
IVORY_DIM = "#C6CEDC"
MUTED = "#8C99B3"

GOLD = "#E8A628"
GOLD_DEEP = "#B87B12"
GOLD_HI = "#FFD277"
CORAL = "#F0605D"
BLUE = "#4A8FE0"
GREEN = "#2FC98C"

PILL_BG = "#0C1D42"
PILL_EDGE = "#2B4676"
CARD_BG = "#081833"
CAPTION_BG = "#050F26"

# ---------------------------------------------------------------- typography
FONT_ROLES = {
    "extrabold": "Montserrat-ExtraBold.ttf",
    "bold": "Montserrat-Bold.ttf",
    "semibold": "Montserrat-SemiBold.ttf",
    "medium": "Montserrat-Medium.ttf",
}
FONT_FALLBACK = {
    "extrabold": "Poppins-Bold.ttf",
    "bold": "Poppins-Bold.ttf",
    "semibold": "Poppins-SemiBold.ttf",
    "medium": "Poppins-Regular.ttf",
}
FONT_DIR_FALLBACK = CHANNEL.parents[1] / "abitinside" / "assets" / "fonts"

SIZE_LOGO_WORD = 40
SIZE_SERIES = 26
SIZE_SECTION = 34
SIZE_SUB = 24
SIZE_LABEL = 30
SIZE_CHIP = 26
SIZE_HERO = 190
SIZE_HERO_SMALL = 120
SIZE_BODY = 36
SIZE_SOURCE = 26
SIZE_CAPTION = 58

# ---------------------------------------------------------------- geometry
CENTER_X = 540.0
LOGO_X = 100.0
LOGO_Y = 118.0
LOGO_R = 30.0
LOGO_BAR_W = 9.0
SERIES_Y = 186.0

SECTION_Y = 428.0
SUB_LABEL_Y = 472.0
STAGE_TOP = 520.0
STAGE_BOTTOM = 1190.0
SOURCE_Y = 1238.0
CAPTION_CENTER_Y = 1332.0
CAPTION_MAX_W = 820.0
CAPTION_MAX_WORDS = 5

# Safe zone. Everything except the logo row stays inside x 100-980 and above
# y 1400. The logo row is the one exemption, kept clear of the top 100 px.
SAFE_X0, SAFE_X1 = 100.0, 980.0
SAFE_TOP = 100.0
SAFE_BOTTOM = 1400.0
LOGO_EXEMPT = (LOGO_X - 30.0, 70.0, SAFE_X1, 210.0)

CENTRE_TOL = 2.0

# ---------------------------------------------------------------- motion
HOOK_LEAD_FRAMES = 12          # narration starts here (~0.4 s)
HEADLINE_IN = 14
HEADLINE_OUT = 10
CAPTION_IN = 5
GAP_AFTER = 9                   # 0.30 s between beats
GAP_BEFORE_REVEAL = 19          # 0.63 s, longer before the reveal
GAP_BEFORE_ENDCARD = 14
WHOOSH_LEAD = 8
RISER_LEAD = 60
REVEAL_SILENCE = 12
MIN_TICK_GAP = 12
SHAKE_MAX_PX = 7.0
PAYOFF_MIN_HOLD_FRAMES = 45
ENDCARD_MIN_FRAMES = 90        # 3.0 s
ENDCARD_MAX_FRAMES = 102       # 3.4 s
MIN_TOTAL_FRAMES = 65 * FPS     # hard gate 65 s
MAX_TOTAL_FRAMES = 175 * FPS    # hard gate 175 s

# ---------------------------------------------------------------- audio
TARGET_I = -16.0
TARGET_TP = -1.5
TARGET_LRA = 6.0
MUSIC_UNDER_NARRATION_DB = -22.0
DUCK_DEPTH_DB = 6.5
DUCK_ATTACK = 0.020
DUCK_RELEASE = 0.400

# ---------------------------------------------------------------- content
BRAND = "Arkad's Ledger"
WORDMARK = "ARKAD'S LEDGER"
SERIES = "MAP OF MONEY"
EPISODE = 2
FORBIDDEN_STRINGS = ("A Bit Inside", "ShakaHub")
DISCLAIMER = "Educational content, not financial advice."


def install_fonts() -> dict:
    """Point the text engine at this channel's TTFs, by path.

    Falls back to the studio's Poppins only if Montserrat is genuinely absent,
    which the doctor records in qa-report.md.
    """
    from videokit import text as vktext

    roles, used_fallback = {}, []
    for role, fn in FONT_ROLES.items():
        p = FONTS_DIR / fn
        if not p.is_file():
            p = FONT_DIR_FALLBACK / FONT_FALLBACK[role]
            used_fallback.append(role)
        roles[role] = str(p)
    vktext.set_fonts(roles)
    return {"roles": roles, "fallback": used_fallback}


def font_report() -> dict:
    from videokit import text as vktext
    try:
        installed = vktext.set_fonts({k: str(FONTS_DIR / v) for k, v in FONT_ROLES.items()
                                      if (FONTS_DIR / v).is_file()})
    except Exception:
        installed = {}
    return installed


_COLOURS = {
    "bg_top": BG_TOP, "bg_bottom": BG_BOTTOM, "bg_corner": BG_CORNER,
    "glow": GLOW, "ray": RAY, "grid": GRID, "dust": DUST,
    "ivory": IVORY, "ivory_dim": IVORY_DIM, "muted": MUTED,
    "gold": GOLD, "gold_deep": GOLD_DEEP, "gold_hi": GOLD_HI,
    "coral": CORAL, "blue": BLUE, "green": GREEN,
    "pill_bg": PILL_BG, "pill_edge": PILL_EDGE, "card_bg": CARD_BG,
    "caption_bg": CAPTION_BG,
}


def rgb(name: str) -> tuple[float, float, float]:
    """Palette lookup by lowercase name: rgb("gold"), rgb("ivory"), ..."""
    from videokit.engine import rgb as _rgb

    try:
        return _rgb(_COLOURS[name.lower()])
    except KeyError:
        raise KeyError(f"unknown colour {name!r}; known: {sorted(_COLOURS)}") from None


PALETTE = {
    "bg_top": BG_TOP, "bg_bottom": BG_BOTTOM, "bg_corner": BG_CORNER,
    "glow": GLOW, "ray": RAY, "grid": GRID, "dust": DUST,
    "ivory": IVORY, "muted": MUTED, "gold": GOLD, "coral": CORAL,
    "blue": BLUE, "green": GREEN, "deep": GOLD_DEEP, "hi": GOLD_HI,
    "dim": IVORY_DIM,
}

GEOM = {
    "stage_top": STAGE_TOP, "stage_bottom": STAGE_BOTTOM,
    "grid_step": 60, "source_y": SOURCE_Y,
}
