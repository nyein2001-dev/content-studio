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

from pathlib import Path

import theme as T

W, H, FPS = T.W, T.H, T.FPS

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
def new_surface(w: int = W, h: int = H) -> tuple[cairo.ImageSurface, cairo.Context]:
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    return surf, cairo.Context(surf)


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


# ------------------------------------------------------------------ shapes
def rrect(cr: cairo.Context, x, y, w, h, r) -> None:
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -1.5708, 0)
    cr.arc(x + w - r, y + h - r, r, 0, 1.5708)
    cr.arc(x + r, y + h - r, r, 1.5708, 3.1416)
    cr.arc(x + r, y + r, r, 3.1416, 4.7124)
    cr.close_path()


def stroke_colour(cr, colour: str, width: float = T.STROKE, alpha: float = 1.0) -> None:
    r, g, b = T.hex_to_rgb(colour)
    cr.set_source_rgba(r, g, b, alpha)
    cr.set_line_width(width)
    cr.stroke()


def fill_colour(cr, colour: str, alpha: float = 1.0) -> None:
    r, g, b = T.hex_to_rgb(colour)
    cr.set_source_rgba(r, g, b, alpha)
    cr.fill()


def line(cr, x0, y0, x1, y1, colour: str, width: float = T.STROKE,
         alpha: float = 1.0, dash=None) -> None:
    r, g, b = T.hex_to_rgb(colour)
    cr.set_source_rgba(r, g, b, alpha)
    cr.set_line_width(width)
    if dash:
        cr.set_dash(dash)
    else:
        cr.set_dash([])
    cr.move_to(x0, y0)
    cr.line_to(x1, y1)
    cr.stroke()
    cr.set_dash([])


def dashed_rect(cr, x, y, w, h, r, colour, width=T.STROKE, alpha=1.0, dash=(10, 12)) -> None:
    rrect(cr, x, y, w, h, r)
    stroke_colour(cr, colour, width, alpha)


def to_rgb_bytes(surf: cairo.ImageSurface) -> bytes:
    """ARGB32 (premultiplied, BGRA in memory) -> packed RGB24 for FFmpeg."""
    h = surf.get_height()
    w = surf.get_width()
    stride = surf.get_stride() // 4
    a = np.frombuffer(surf.get_data(), dtype=np.uint8).reshape(h, stride, 4)
    return np.ascontiguousarray(a[:, :w, [2, 1, 0]]).tobytes()


# ------------------------------------------------------------------ the loop
_STATE: dict = {}


def _init_worker(timeline_path: str, frames_path: str) -> None:
    import json
    import sys

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    install_fonts()
    surf, cr = new_surface()
    bg = build_background()
    _STATE["surf"] = surf
    _STATE["cr"] = cr
    _STATE["txt"] = Text(cr)
    _STATE["bg"] = bg
    _STATE["tl"] = json.loads(Path(timeline_path).read_text(encoding="utf-8"))


def _render_chunk(task):
    start, count = task
    from scenes import compose_frame

    cr = _STATE["cr"]
    txt = _STATE["txt"]
    tl = _STATE["tl"]
    bg = _STATE["bg"]
    surf = _STATE["surf"]
    out = []
    for i in range(start, start + count):
        cr.set_operator(cairo.OPERATOR_OVER)
        cr.paint()
        compose_frame(cr, txt, i, tl, bg, _STATE)
        surf.flush()
        out.append(to_rgb_bytes(surf))
    return start, b"".join(out)


def render_to_ffmpeg(out_path, timeline_path: str, workers: int = 2,
                     chunk: int = 8, progress=None) -> int:
    """Render every frame and pipe raw RGB straight into FFmpeg's stdin.

    No PNG sequence is ever written to disk.
    """
    import json
    import multiprocessing as mp
    import os
    import subprocess
    import time

    tl = json.loads(Path(timeline_path).read_text(encoding="utf-8"))
    total = tl["total_frames"]
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        os.environ["FFMPEG"], "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
        "-i", "-",
        "-an",
        "-c:v", "libx264", "-profile:v", "high", "-level", "4.2",
        "-pix_fmt", "yuv420p", "-crf", "16", "-preset", "slow", "-tune", "animation",
        "-g", "60", "-bf", "2",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
        "-r", str(FPS), "-video_track_timescale", "90000",
        str(out_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    tasks = [(s, min(chunk, total - s)) for s in range(0, total, chunk)]

    t0 = time.time()
    written = 0
    ctx = mp.get_context("fork")
    try:
        if workers <= 1:
            _init_worker(timeline_path, str(out_path))
            for t in tasks:
                _, blob = _render_chunk(t)
                proc.stdin.write(blob)
                written += t[1]
                if progress:
                    progress(written, total, time.time() - t0)
        else:
            with ctx.Pool(processes=workers, initializer=_init_worker,
                          initargs=(timeline_path, str(out_path))) as pool:
                for _, blob in pool.imap(_render_chunk, tasks, chunksize=1):
                    proc.stdin.write(blob)
                    written += blob.__len__() // (W * H * 3)
                    if progress:
                        progress(written, total, time.time() - t0)
    finally:
        proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", "replace")
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg encode failed ({rc}): {err[:600]}")
    return total