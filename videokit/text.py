#!/usr/bin/env python3
"""Shared text engine: measure and draw anti-aliased text with Pillow + pycairo.

Channel-independent. Fonts are loaded by FILE PATH (never by system lookup), so a
channel can never silently inherit a system font. Each channel installs its own
TTF map through :func:`set_fonts`.

Rendered glyph runs are cached, so repeating the same string on many frames costs
one Pillow rasterisation plus a blit.
"""
from __future__ import annotations

import functools
from pathlib import Path

import cairo
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONTS: dict[str, str] = {}
SUPERSAMPLE = 2  # rasterise large then downsample: crisper edges at hero sizes


def set_fonts(mapping: dict[str, str | Path]) -> None:
    """Install the TTF map. Keys are roles: bold, semibold, medium, extrabold, ..."""
    global FONTS
    FONTS = {k: str(Path(v)) for k, v in mapping.items()}
    _font.cache_clear()
    _glyphs.cache_clear()


@functools.lru_cache(maxsize=256)
def _font(role: str, size_px: int) -> ImageFont.FreeTypeFont:
    try:
        path = FONTS[role]
    except KeyError as exc:
        raise KeyError(
            f"no font installed for role {role!r}; call text.set_fonts() first "
            f"(known roles: {sorted(FONTS)})"
        ) from exc
    if not Path(path).is_file():
        raise FileNotFoundError(f"font file missing for role {role!r}: {path}")
    return ImageFont.truetype(path, size_px)


def _scaled(role: str, size: float) -> tuple[str, int]:
    return role, max(1, int(round(size * SUPERSAMPLE)))


def advance(text: str, role: str, size: float) -> float:
    """Horizontal advance in device pixels at logical `size`."""
    if not text:
        return 0.0
    key, px = _scaled(role, size)
    f = _font(key, px)
    return f.getlength(text) / SUPERSAMPLE


def line_height(role: str, size: float) -> float:
    key, px = _scaled(role, size)
    f = _font(key, px)
    a, d = f.getmetrics()
    return (a + d) / SUPERSAMPLE


def ascent(role: str, size: float) -> float:
    key, px = _scaled(role, size)
    a, _ = _font(key, px).getmetrics()
    return a / SUPERSAMPLE


def cap_height(role: str, size: float) -> float:
    """Height of a capital letter, used to place headlines optically centred."""
    key, px = _scaled(role, size)
    f = _font(key, px)
    box = f.getbbox("H")
    return (box[3] - box[1]) / SUPERSAMPLE


@functools.lru_cache(maxsize=4096)
def _glyphs(text: str, role: str, size: float) -> tuple[np.ndarray, int, int]:
    """Render one string to a premultiplied BGRA tile plus its bearing.

    Returns (tile, offset_x, offset_y) where offset_* is in logical pixels from
    the draw origin to the tile's top-left corner.
    """
    key, px = _scaled(role, size)
    f = _font(key, px)
    box = f.getbbox(text)  # (x0, y0, x1, y1) in raster pixels, anchor la
    w = max(1, box[2] - box[0])
    h = max(1, box[3] - box[1])
    img = Image.new("L", (w, h), 0)
    ImageDraw.Draw(img).text((-box[0], -box[1]), text, font=f, fill=255, anchor="la")
    if SUPERSAMPLE > 1:
        img = img.resize((max(1, w // SUPERSAMPLE), max(1, h // SUPERSAMPLE)), Image.LANCZOS)
    return np.asarray(img, dtype=np.uint8).copy(), box[0] // SUPERSAMPLE, box[1] // SUPERSAMPLE


def measure(text: str, role: str, size: float) -> tuple[float, float]:
    """(advance, line height) for one line."""
    return advance(text, role, size), line_height(role, size)


def draw(cr: cairo.Context, x: float, y: float, text: str, role: str, size: float,
         rgb: tuple[float, float, float], alpha: float = 1.0) -> float:
    """Draw one run with its box origin at (x, y). Returns the advance."""
    if not text or alpha <= 0.004:
        return 0.0
    tile, ox, oy = _glyphs(text, role, float(size))
    h, w = tile.shape
    alpha_map = np.clip(tile.astype(np.float32) * float(alpha), 0.0, 255.0).astype(np.uint8)

    # cairo FORMAT_ARGB32 is a native-endian uint32 (0xAARRGGBB), so the memory
    # order on a little-endian machine is B, G, R, A - not RGB.
    base = np.array([np.clip(c, 0.0, 1.0) * 255.0 for c in rgb], dtype=np.float32)
    buf = np.zeros((h, w, 4), dtype=np.uint8)
    buf[:, :, :3] = (base[None, None, ::-1] * (alpha_map[:, :, None] / 255.0)).astype(np.uint8)
    buf[:, :, 3] = alpha_map

    surf = cairo.ImageSurface.create_for_data(bytearray(buf.tobytes()), cairo.FORMAT_ARGB32, w, h, w * 4)
    cr.save()
    cr.set_operator(cairo.OPERATOR_OVER)
    cr.set_source_surface(surf, round(x) - ox, round(y) - oy)
    cr.paint()
    cr.restore()
    return advance(text, role, size)


def glyph_coverage(chars: str, role: str) -> set[str]:
    """Which of `chars` the installed font cannot render (empty = all covered)."""
    from fontTools.ttLib import TTFont

    path = FONTS[role]
    cmap = set()
    tt = TTFont(path, fontNumber=0)
    for table in tt["cmap"].tables:
        cmap.update(table.cmap.keys())
    return {c for c in set(chars) if ord(c) not in cmap}