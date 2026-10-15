#!/usr/bin/env python3
"""Shared pycairo frame engine: surfaces, cached backgrounds, glows, shapes.

Channel-independent. A channel passes its own palette and geometry in as plain
arguments or through a small style object; nothing here hard-codes a colour.

Rendering is deterministic: frame N is a pure function of N and the timeline.
No PNG sequence is ever written to disk; raw RGB goes straight to FFmpeg's stdin.
"""
from __future__ import annotations

import math
import os
import subprocess
import time
from pathlib import Path

import cairo
import numpy as np

from . import motion, text as vktext

W, H, FPS = 1080, 1920, 30


# ------------------------------------------------------------------ surfaces
def new_surface(w: int = W, h: int = H) -> tuple[cairo.ImageSurface, cairo.Context]:
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    return surf, cairo.Context(surf)


def rgb(hex_colour: str) -> tuple[float, float, float]:
    h = hex_colour.lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)


def with_alpha(hex_colour: str, alpha: float) -> tuple[float, float, float, float]:
    return (*rgb(hex_colour), float(alpha))


def relative_luminance(hex_colour: str) -> float:
    def ch(v: float) -> float:
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb(hex_colour)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast_ratio(fg: str, bg: str) -> float:
    a, b = relative_luminance(fg), relative_luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


# ------------------------------------------------------------------ background
_BG_CACHE: dict[tuple, cairo.ImageSurface] = {}


def build_background(palette: dict, geom: dict, seed: int = 20261013,
                     dust: int = 170, pad: int = 96,
                     grid: bool = True) -> cairo.ImageSurface:
    """Deep-navy vertical gradient + vignette + faint ray texture + gold dust + dither.

    Baked once and reused on every frame, so the drift comes from compositing a
    sub-rectangle of this plate rather than from re-rasterising it.
    """
    key = (tuple(sorted(palette.items())), tuple(sorted(geom.items())), seed, dust, grid)
    hit = _BG_CACHE.get(key)
    if hit is not None:
        return hit

    w, h = W + pad, H + pad
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(surf)

    # vertical gradient
    g = cairo.LinearGradient(0, 0, 0, h)
    g.add_color_stop_rgba(0.00, *with_alpha(palette["bg_top"], 1.0))
    g.add_color_stop_rgba(0.52, *with_alpha(palette["bg_top"], 1.0))
    g.add_color_stop_rgba(1.00, *with_alpha(palette["bg_bottom"], 1.0))
    cr.set_source(g)
    cr.paint()

    # faint light rays from the upper centre
    if grid:
        cx = w / 2.0
        top = -h * 0.18
        for i in range(-7, 8):
            ang = -0.5 + i * 0.075
            cr.set_source_rgba(*rgb(palette["ray"]), 0.030)
            cr.move_to(cx, top)
            cr.line_to(cx + math.tan(ang) * h * 2.4, h)
            cr.close_path()
            cr.fill()

    # soft vignette toward the corners
    vg = cairo.RadialGradient(w / 2, h / 2, min(w, h) * 0.28,
                              w / 2, h / 2, max(w, h) * 0.72)
    vg.add_color_stop_rgba(0.0, *with_alpha(palette["bg_corner"], 0.0))
    vg.add_color_stop_rgba(1.0, *with_alpha(palette["bg_corner"], 0.55))
    cr.set_source(vg)
    cr.paint()

    # centred glow behind the visual band
    cxm = w / 2.0
    cym = (geom["stage_top"] + geom["stage_bottom"]) / 2.0
    rg = cairo.RadialGradient(cxm, cym, 40, cxm, cym, 660)
    rg.add_color_stop_rgba(0.00, *with_alpha(palette["glow"], 0.50))
    rg.add_color_stop_rgba(0.55, *with_alpha(palette["glow"], 0.17))
    rg.add_color_stop_rgba(1.00, *with_alpha(palette["glow"], 0.00))
    cr.set_source(rg)
    cr.paint()

    # very light grid, confined to the visual band
    if grid:
        step = geom.get("grid_step", 60)
        cr.set_line_width(1.0)
        for gx in range(0, w, step):
            cr.set_source_rgba(*rgb(palette["grid"]), 0.16)
            cr.move_to(gx + 0.5, geom["stage_top"])
            cr.line_to(gx + 0.5, geom["stage_bottom"])
            cr.stroke()
        for gy in range(int(geom["stage_top"]), int(geom["stage_bottom"]), step):
            cr.set_source_rgba(*rgb(palette["grid"]), 0.16)
            cr.move_to(0, gy + 0.5)
            cr.line_to(w, gy + 0.5)
            cr.stroke()

    # slow drifting gold dust
    rng = np.random.default_rng(seed)
    dx = rng.uniform(0, w, dust)
    dy = rng.uniform(0, h, dust)
    dr = rng.uniform(1.0, 2.8, dust)
    da = rng.uniform(0.10, 0.52, dust)
    for i in range(dust):
        cr.set_source_rgba(*rgb(palette["dust"]), float(da[i]))
        cr.arc(float(dx[i]), float(dy[i]), float(dr[i]), 0, 6.2832)
        cr.fill()

    # deterministic +/-1 dither so 8-bit navy never bands
    data = np.frombuffer(surf.get_data(), dtype=np.uint8).copy()
    stride = surf.get_stride() // 4
    view = data.reshape(surf.get_height(), stride, 4)[:, :w, :3].astype(np.int16)
    view += rng.integers(-1, 2, size=view.shape[:2])[:, :, None]
    np.clip(view, 0, 255, out=view)
    data.reshape(surf.get_height(), stride, 4)[:, :w, :3] = view.astype(np.uint8)
    surf.flush()
    surf.mark_dirty()
    _BG_CACHE[key] = surf
    return surf


def math_tan(ang: float) -> float:
    return math.tan(ang)


# ------------------------------------------------------------------ glow
_GLOW: dict[tuple, cairo.ImageSurface] = {}


def glow(colour: str, radius: int = 320, strength: float = 0.55) -> cairo.ImageSurface:
    key = (colour, radius, round(strength, 2))
    s = _GLOW.get(key)
    if s is None:
        size = radius * 2
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        cr = cairo.Context(s)
        r, g, b = rgb(colour)
        steps = 26
        for i in range(steps, 0, -1):
            t = i / steps
            cr.set_source_rgba(r, g, b, strength * (1.0 - t) ** 2.1)
            cr.arc(radius, radius, radius * t, 0, 6.2832)
            cr.fill()
        _GLOW[key] = s
    return s


def paint_glow(cr: cairo.Context, cx: float, cy: float, radius: int = 320,
               colour: str = "#E8A628", strength: float = 0.5,
               scale: float = 1.0) -> None:
    s = glow(colour, radius, strength)
    cr.save()
    cr.set_operator(cairo.OPERATOR_OVER)
    if scale != 1.0:
        r = radius * scale
        cr.translate(cx, cy)
        cr.scale(scale, scale)
        cr.set_source_surface(s, -r, -r)
        cr.get_source().set_matrix(cairo.Matrix(1 / scale, 0, 0, 1 / scale, 0, 0))
    else:
        cr.set_source_surface(s, cx - radius, cy - radius)
    cr.paint()
    cr.restore()


# ------------------------------------------------------------------ shapes
def rrect(cr: cairo.Context, x, y, w, h, r) -> None:
    r = min(r, abs(w) / 2, abs(h) / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -1.5708, 0)
    cr.arc(x + w - r, y + h - r, r, 0, 1.5708)
    cr.arc(x + r, y + h - r, r, 1.5708, 3.1416)
    cr.arc(x + r, y + r, r, 3.1416, 4.7124)
    cr.close_path()


def fill(cr, colour: str, alpha: float = 1.0) -> None:
    cr.set_source_rgba(*with_alpha(colour, alpha))
    cr.fill()


def stroke(cr, colour: str, width: float = 3.0, alpha: float = 1.0) -> None:
    cr.set_source_rgba(*with_alpha(colour, alpha))
    cr.set_line_width(width)
    cr.stroke()


def line(cr, x0, y0, x1, y1, colour: str, width: float = 3.0,
         alpha: float = 1.0, dash=None) -> None:
    cr.set_source_rgba(*with_alpha(colour, alpha))
    cr.set_line_width(width)
    cr.set_dash(list(dash) if dash else [])
    cr.move_to(x0, y0)
    cr.line_to(x1, y1)
    cr.stroke()
    cr.set_dash([])


def dashed_rect(cr, x, y, w, h, r, colour, width=3.0, alpha=1.0, dash=(10, 12)) -> None:
    rrect(cr, x, y, w, h, r)
    stroke(cr, colour, width, alpha)


def circle(cr, cx, cy, r) -> None:
    cr.new_sub_path()
    cr.arc(cx, cy, r, 0, 6.2832)
    cr.close_path()


def to_rgb_bytes(surf: cairo.ImageSurface) -> bytes:
    """ARGB32 (premultiplied, BGRA on little-endian) -> packed RGB24 for FFmpeg."""
    h = surf.get_height()
    w = surf.get_width()
    stride = surf.get_stride() // 4
    a = np.frombuffer(surf.get_data(), dtype=np.uint8).reshape(h, stride, 4)
    return np.ascontiguousarray(a[:, :w, [2, 1, 0]]).tobytes()


# ------------------------------------------------------------------ the loop
ENCODE_FLAGS = [
    "-c:v", "libx264", "-profile:v", "high", "-level", "4.2",
    "-pix_fmt", "yuv420p", "-crf", "16", "-preset", "slow", "-tune", "animation",
    "-g", "60", "-bf", "2",
    "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
]


def render_to_ffmpeg(out_path, total_frames: int, compose_frame, *,
                     width: int = W, height: int = H, fps: int = FPS,
                     workers: int = 2, chunk: int = 12, progress=None,
                     ffmpeg: str | None = None, crf: int = 16,
                     preset: str = "slow") -> int:
    """Render every frame and pipe raw RGB straight into FFmpeg's stdin.

    `compose_frame(cr, frame)` must draw one complete frame onto `cr`.
    Returns the number of frames written.
    """
    ffmpeg = ffmpeg or os.environ["FFMPEG"]
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
        "-r", str(fps), "-i", "-", "-an",
        *ENCODE_FLAGS, "-crf", str(crf), "-preset", preset,
        "-r", str(fps), "-video_track_timescale", "90000",
        str(out_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    surf, cr = new_surface(width, height)
    tasks = [(s, min(chunk, total_frames - s)) for s in range(0, total_frames, chunk)]
    t0 = time.time()
    written = 0
    try:
        for start, count in tasks:
            parts = []
            for i in range(start, start + count):
                # Clear, then hand the scene OVER compositing. Leaving
                # OPERATOR_SOURCE set here makes every fill() in the scene
                # REPLACE the destination instead of compositing over it, which
                # punches holes in the background plate.
                cr.set_operator(cairo.OPERATOR_SOURCE)
                cr.paint()
                cr.set_operator(cairo.OPERATOR_OVER)
                compose_frame(cr, i)
                surf.flush()
                parts.append(to_rgb_bytes(surf))
            proc.stdin.write(b"".join(parts))
            written += count
            if progress:
                progress(written, total_frames, time.time() - t0)
    finally:
        try:
            proc.stdin.close()
        except (BrokenPipeError, ValueError):
            pass
    err = proc.stderr.read().decode("utf-8", "replace")
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg encode failed ({rc}): {err[:800]}")
    return written