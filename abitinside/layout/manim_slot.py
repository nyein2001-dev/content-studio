"""Charts and counting stats are Manim frames, cached by content, blitted by cairo.

A missing Manim install is a hard error for these components. Nothing here
falls back to a cairo polyline or a toy font.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

from layout.errors import LayoutError
from layout.fonts import install_fonts
from layout.spec import ABIT

_CACHE = ABIT / ".cache" / "manim-slots"


def require_manim():
    try:
        import manim
    except ImportError as exc:
        raise LayoutError(
            "manim",
            "R09",
            "manim is not installed, so a chart or counting stat cannot render",
            "Run bash setup.sh. A failed Manim install stops Chart and Stat; "
            "there is no cairo fallback and no toy font.",
        ) from exc
    return manim


def chart_image(points: tuple[tuple[float, float], ...], width: int, height: int, color: str) -> Image.Image:
    """Transparent plot of a series. The caller blits it into the slot."""
    require_manim()
    payload = {"points": points, "width": width, "height": height, "color": color, "kind": "chart"}
    return _cached(payload, lambda: _render_chart(points, width, height, color))


def stat_image(text: str, width: int, height: int, color: str) -> Image.Image:
    """The reserved final value, drawn by Manim into the stat slot."""
    require_manim()
    payload = {"text": text, "width": width, "height": height, "color": color, "kind": "stat"}
    return _cached(payload, lambda: _render_stat(text, width, height, color))


def _cached(payload: dict, build) -> Image.Image:
    install_fonts()
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    path = _CACHE / f"{digest}.png"
    if path.is_file():
        return Image.open(path).convert("RGBA")
    _CACHE.mkdir(parents=True, exist_ok=True)
    image = build()
    image.save(path)
    return image


def _render_chart(points, width: int, height: int, color: str) -> Image.Image:
    manim = require_manim()
    import numpy as np

    width = max(8, int(width))
    height = max(8, int(height))
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1.0)
    span_y = max(max_y - min_y, 1.0)

    def build(scene):
        corners = []
        for x, y in points:
            nx = (x - min_x) / span_x * 6 - 3
            ny = (1.0 - (y - min_y) / span_y) * 3 - 1.5
            corners.append(np.array([nx, ny, 0.0]))
        graph = manim.VMobject()
        graph.set_points_as_corners(corners)
        graph.set_stroke(color, width=4)
        scene.add(graph)

    return _scene_png(build, width, height)


def _render_stat(text: str, width: int, height: int, color: str) -> Image.Image:
    manim = require_manim()

    def build(scene):
        label = manim.Text(text, font="ABit Mono", color=color)
        label.set_height(min(2.4, max(0.4, height / 80)))
        scene.add(label)

    return _scene_png(build, max(8, int(width)), max(8, int(height)))


def _scene_png(build, width: int, height: int) -> Image.Image:
    manim = require_manim()
    media = _CACHE / "media"
    media.mkdir(parents=True, exist_ok=True)
    with manim.tempconfig({
        "pixel_width": width,
        "pixel_height": height,
        "frame_width": 8.0,
        "frame_height": 8.0 * height / max(1, width),
        "background_opacity": 0,
        "media_dir": str(media),
        "renderer": "cairo",
        "format": "png",
        "save_last_frame": True,
        "write_to_movie": False,
        "preview": False,
        "disable_caching": True,
        "verbosity": "ERROR",
        "progress_bar": "none",
    }):
        class _Slot(manim.Scene):
            def construct(self):
                build(self)

        scene = _Slot()
        scene.render()
    pngs = sorted(media.rglob("*.png"), key=lambda item: item.stat().st_mtime)
    if not pngs:
        raise LayoutError(
            "manim",
            "R09",
            "manim rendered no frame for this slot",
            "Re-run bash setup.sh so Manim can write a transparent PNG.",
        )
    image = Image.open(pngs[-1]).convert("RGBA")
    return image.resize((width, height), Image.Resampling.LANCZOS)
