#!/usr/bin/env python3
"""
A Bit Inside - the frame engine (section 8).

Native pycairo at 1080x1920. No PNG sequences ever touch the disk: each worker
renders a chunk of frames to raw RGB and hands it to the parent, which pipes it
straight into FFmpeg's stdin.

Everything expensive is built once and reused:
  * the background (gradient + glow + starfield + dither) is a cached surface
  * the radial glow is one pre-blurred sprite, composited with OVER
  * font selections are cached per context
Rendering is deterministic: frame N depends only on frame N and timeline.json.
"""
from __future__ import annotations

import cairo
import numpy as np
import sys

from pathlib import Path

import theme as T

# Channel-independent drawing primitives and the frame->FFmpeg driver now live in
# the shared package, so both channels rasterise, glow and pipe frames identically.
# Only the brand-specific background plate, the brand glow tint and the text
# binding stay here.
_ROOT = Path(__file__).resolve().parents[4]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from videokit.engine import (  # noqa: E402,F401
    FPS,
    H,
    W,
    ENCODE_FLAGS,
    dashed_rect,
    line,
    new_surface,
    render_to_ffmpeg,
    rrect,
    to_rgb_bytes,
)

W, H, FPS = T.W, T.H, T.FPS


def fill_colour(cr, colour: str, alpha: float = 1.0) -> None:
    from videokit.engine import fill

    fill(cr, colour, alpha)


def stroke_colour(cr, colour: str, width: float = T.STROKE, alpha: float = 1.0) -> None:
    from videokit.engine import stroke

    stroke(cr, colour, width, alpha)


def install_fonts() -> str:
    """Point fontconfig at the four TTFs this project owns. Idempotent."""
    import os

    abit = T.ABIT
    fdir = abit / "assets" / "fonts"
    cache = abit / ".cache" / "fontconfig"
    cache.mkdir(parents=True, exist_ok=True)
    tpl = (abit / "assets" / "fonts.conf.tpl")
    conf = abit / "assets" / "fonts.conf"
    subs = {
        "FONTS_DIR": str(fdir),
        "CACHE_DIR": str(cache),
        "FONT_POPPINSBOLD": str(fdir / "Poppins-Bold.ttf"),
        "FONT_POPPINSSEMIBOLD": str(fdir / "Poppins-SemiBold.ttf"),
        "FONT_POPPINSNORMAL": str(fdir / "Poppins-Regular.ttf"),
        "FONT_JBMONO": str(fdir / "JetBrainsMono.ttf"),
    }
    text = tpl.read_text(encoding="utf-8")
    for k, v in subs.items():
        text = text.replace(k, v)
    conf.write_text(text, encoding="utf-8")
    os.environ["FONTCONFIG_FILE"] = str(conf)
    os.environ["FONTCONFIG_PATH"] = str(abit / "assets")
    return str(conf)


# ------------------------------------------------------------------ surfaces
def build_background() -> cairo.ImageSurface:
    """Deep navy vertical gradient + a soft glow behind the illustration + a
    sparse starfield + +/-1 level dither. Baked once, reused on every frame."""
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W + 96, H + 96)
    cr = cairo.Context(surf)

    # base vertical gradient
    g = cairo.LinearGradient(0, 0, 0, H)
    g.add_color_stop_rgba(0.0, *T.with_alpha(T.BG_TOP, 1.0))
    g.add_color_stop_rgba(0.55, *T.with_alpha(T.BG_TOP, 1.0))
    g.add_color_stop_rgba(1.0, *T.with_alpha(T.BG_BOTTOM, 1.0))
    cr.set_source(g)
    cr.paint()

    # radial glow centred on the illustration area
    rg = cairo.RadialGradient(W / 2, (T.ILLUSTRATION_TOP + T.ILLUSTRATION_BOTTOM) / 2, 40,
                              W / 2, (T.ILLUSTRATION_TOP + T.ILLUSTRATION_BOTTOM) / 2, 620)
    rg.add_color_stop_rgba(0.0, *T.with_alpha(T.GLOW, T.GLOW_ALPHA))
    rg.add_color_stop_rgba(0.55, *T.with_alpha(T.GLOW, 0.18))
    rg.add_color_stop_rgba(1.0, *T.with_alpha(T.GLOW, 0.0))
    cr.set_source(rg)
    cr.paint()

    # sparse starfield
    rng = np.random.default_rng(0xAB17)
    n_stars = 150
    sx = rng.uniform(0, W + 96, n_stars)
    sy = rng.uniform(0, H + 96, n_stars)
    sr = rng.uniform(0.9, 2.1, n_stars)
    sa = rng.uniform(0.10, 0.38, n_stars)
    for i in range(n_stars):
        a = float(sa[i])
        cr.set_source_rgba(*T.hex_to_rgb(T.STAR), a)
        cr.arc(float(sx[i]), float(sy[i]), float(sr[i]), 0, 6.2832)
        cr.fill()

    # dither: +/-1 level of deterministic noise, baked in so it cannot flicker
    data = np.frombuffer(surf.get_data(), dtype=np.uint8).copy()
    stride = surf.get_stride() // 4
    view = data.reshape(surf.get_height(), stride, 4)[:, : W + 96, :3].astype(np.int16)
    noise = rng.integers(-1, 2, size=view.shape[:2])[:, :, None]
    view += noise
    np.clip(view, 0, 255, out=view)
    data.reshape(surf.get_height(), stride, 4)[:, : W + 96, :3] = view.astype(np.uint8)
    surf.mark_dirty()
    return surf


def build_glow_sprite(radius: int = 320, colour: str = T.CYAN,
                      strength: float = 0.55) -> cairo.ImageSurface:
    """A soft radial glow, blurred by construction (no per-frame blur cost)."""
    size = radius * 2
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    cr = cairo.Context(surf)
    r, g, b = T.hex_to_rgb(colour)
    steps = 26
    for i in range(steps, 0, -1):
        t = i / steps
        a = strength * (1.0 - t) ** 2.1
        cr.set_source_rgba(r, g, b, a)
        cr.arc(radius, radius, radius * t, 0, 6.2832)
        cr.fill()
    return surf


_GLOW: dict[tuple, cairo.ImageSurface] = {}


def glow(colour: str = T.CYAN, radius: int = 320, strength: float = 0.55) -> cairo.ImageSurface:
    key = (colour, radius, round(strength, 2))
    s = _GLOW.get(key)
    if s is None:
        s = build_glow_sprite(radius, colour, strength)
        _GLOW[key] = s
    return s


def paint_glow(cr: cairo.Context, cx: float, cy: float, radius: int = 320,
               colour: str = T.CYAN, strength: float = 0.5) -> None:
    s = glow(colour, radius, strength)
    cr.set_operator(cairo.OPERATOR_OVER)
    cr.set_source_surface(s, cx - radius, cy - radius)


# ------------------------------------------------------------------ text
class Text:
    """Cached font selection + measurement + coloured runs on one line."""

    def __init__(self, cr: cairo.Context):
        self.cr = cr
        self._cur = None

    def font(self, family: str, size: float, weight: str = "bold") -> None:
        if family == "mono":
            self._key = "mono"
        elif weight == "bold":
            self._key = "bold"
        else:
            self._key = "regular"
        self._size = float(size)
        self._cur = (family, size, weight)

    def width(self, s: str) -> float:
        from layout.text import measure

        return measure(s, self._key, self._size).advance

    def height(self, s: str) -> float:
        from layout.text import measure

        return measure(s, self._key, self._size).height

    def ascent(self) -> float:
        return self._size * 0.8

    def draw(self, x: float, y: float, s: str, colour: str, alpha: float = 1.0) -> None:
        from layout.text import draw as paint

        red, green, blue = T.hex_to_rgb(colour)
        self.cr.save()
        self.cr.translate(x, y)
        paint(self.cr, s, self._key, self._size, (red, green, blue), alpha)
        self.cr.restore()

    def draw_c(self, xc: float, y: float, s: str, colour: str,
               alpha: float = 1.0) -> float:
        """Draw with xc as the horizontal CENTRE. Returns the text width."""
        w = self.width(s)
        self.draw(xc - w / 2, y, s, colour, alpha)
        return w

    def draw_r(self, xr: float, y: float, s: str, colour: str,
               alpha: float = 1.0) -> float:
        """Draw with xr as the horizontal RIGHT edge. Returns the text width."""
        w = self.width(s)
        self.draw(xr - w, y, s, colour, alpha)
        return w

    def runs(self, x: float, y: float, runs, alpha: float = 1.0,
             align: str = "center") -> float:
        """runs = [(text, colour_or_None), ...] drawn on one baseline."""
        total = sum(self.width(t) for t, _ in runs)
        if align == "center":
            x = x - total / 2
        elif align == "right":
            x = x - total
        for t, colour in runs:
            if colour:
                self.draw(x, y, t, colour, alpha)
            x += self.width(t)
        return total


def wrapped_lines(text: str, max_w: float, fn) -> list[str]:
    """Greedy wrap to a pixel width. Returns at most `lines` lines."""
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if cur and fn.width(trial) > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines
