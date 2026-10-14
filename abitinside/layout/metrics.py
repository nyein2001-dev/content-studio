"""Ink metrics from the bundled font files. Advance widths are not used for fit."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from PIL import ImageFont

from layout.fonts import font_file, install_fonts
from layout.spec import load_spec


@dataclass(frozen=True)
class GlyphInk:
    width: float
    height: float
    bearing_x: float
    bearing_y: float
    advance: float


@lru_cache(maxsize=256)
def _font(key: str, size: int) -> ImageFont.FreeTypeFont:
    install_fonts()
    return ImageFont.truetype(str(font_file(key)), size=size)


def measure(text: str, font_key: str, size: float) -> GlyphInk:
    """Ink box of `text` at `size` px. Empty text has a zero box and the font's advance of a space is unused."""
    if text == "":
        return GlyphInk(0.0, 0.0, 0.0, 0.0, 0.0)
    font = _font(font_key, int(round(size)))
    left, top, right, bottom = font.getbbox(text)
    advance = float(font.getlength(text))
    return GlyphInk(
        width=float(right - left),
        height=float(bottom - top),
        bearing_x=float(left),
        bearing_y=float(top),
        advance=advance,
    )


def font_key_for(role: str) -> str:
    spec = load_spec()
    try:
        return spec["type"][role]["font"]
    except KeyError as exc:
        raise KeyError(f"type role {role} is not in layout_spec.yaml") from exc
