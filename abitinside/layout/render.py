"""Cairo compositor. Glyphs are rasterized from the bundled TTF and painted on."""
from __future__ import annotations

import cairo
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from layout.brand import colour
from layout.errors import LayoutError
from layout.fonts import font_file, install_fonts
from layout.model import Node, PlacedScene
from layout.spec import load_spec


def render_frame(scene: PlacedScene, frame: int = 0) -> Image.Image:
    if type(scene) is not PlacedScene:
        raise LayoutError(
            "frame", "LR-11",
            "the renderer received raw coordinates",
            "Pass a solved PlacedScene. Do not call the renderer with x, y, or a font size.",
        )
    install_fonts()
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, scene.width, scene.height)
    context = cairo.Context(surface)
    _gradient(context, scene.width, scene.height)
    spec = load_spec()
    for node in sorted(scene.nodes, key=lambda item: (item.z, item.id)):
        _draw(context, scene, node, frame, spec)
    return surface_image(surface)


def surface_image(surface: cairo.ImageSurface) -> Image.Image:
    surface.flush()
    width, height = surface.get_width(), surface.get_height()
    raw = np.ndarray(
        shape=(height, surface.get_stride() // 4, 4),
        dtype=np.uint8,
        buffer=surface.get_data(),
    )
    bgra = raw[:, :width, :].copy()
    rgba = np.empty_like(bgra)
    rgba[:, :, 0] = bgra[:, :, 2]
    rgba[:, :, 1] = bgra[:, :, 1]
    rgba[:, :, 2] = bgra[:, :, 0]
    rgba[:, :, 3] = 255
    # Un-premultiply when the pixel is translucent.
    alpha = bgra[:, :, 3:4].astype(np.float32)
    visible = alpha[:, :, 0] > 0
    for channel in range(3):
        src = bgra[:, :, 2 - channel].astype(np.float32)
        fixed = np.where(visible, np.clip(src * 255.0 / np.maximum(alpha[:, :, 0], 1), 0, 255), 0)
        rgba[:, :, channel] = fixed.astype(np.uint8)
    rgba[:, :, 3] = bgra[:, :, 3]
    return Image.fromarray(rgba, "RGBA").convert("RGB")


def _draw(context, scene: PlacedScene, node: Node, frame: int, spec: dict) -> None:
    alpha = opacity_at(node, frame)
    if alpha <= 0.01 or node.kind in ("connector_request", "slot", "tick_label"):
        return
    if node.kind == "connector":
        _connector(context, node, alpha)
    elif node.kind == "text":
        _paint_text(context, node, alpha)
    elif node.kind == "series" and node.role == "bar":
        _bars(context, node, alpha, spec)
    elif node.kind == "series":
        _polyline(context, node, alpha)
    elif node.kind in ("figure", "meter", "underline", "cursor", "axis") or node.fill:
        _round(context, node, alpha, spec, fill=True)
        if node.stroke:
            _round(context, node, alpha, spec, fill=False)
    elif node.stroke or node.kind in ("chip", "card", "line_chart", "bar_chart", "timeline", "code_panel", "stat", "severity_meter"):
        _round(context, node, alpha, spec, fill=True)
        _round(context, node, alpha, spec, fill=False)


def opacity_at(node: Node, frame: int) -> float:
    motion = node.motion
    if motion is None:
        return 1.0
    if frame <= motion.start:
        return motion.opacity0
    if frame >= motion.end:
        return motion.opacity1
    span = max(1, motion.end - motion.start)
    t = (frame - motion.start) / span
    return motion.opacity0 + (motion.opacity1 - motion.opacity0) * t


def _gradient(context, width, height) -> None:
    paint = cairo.LinearGradient(0, 0, 0, height)
    top = _unit(colour("bg_top"))
    bottom = _unit(colour("bg_bottom"))
    paint.add_color_stop_rgb(0, *top)
    paint.add_color_stop_rgb(1, *bottom)
    context.set_source(paint)
    context.paint()


def _round(context, node: Node, alpha: float, spec: dict, fill: bool) -> None:
    radius = min(float(spec["spacing"]["radius"]), node.rect.w / 2, node.rect.h / 2)
    rect = node.rect
    context.new_sub_path()
    context.arc(rect.x + rect.w - radius, rect.y + radius, radius, -1.5708, 0)
    context.arc(rect.x + rect.w - radius, rect.y + rect.h - radius, radius, 0, 1.5708)
    context.arc(rect.x + radius, rect.y + rect.h - radius, radius, 1.5708, 3.1416)
    context.arc(rect.x + radius, rect.y + radius, radius, 3.1416, 4.7124)
    context.close_path()
    red, green, blue = _unit(colour(node.color if node.color in _known() else "cyan"))
    if fill:
        strength = 1.0 if node.kind in ("figure", "meter", "underline", "cursor", "axis") else 0.16
        context.set_source_rgba(red, green, blue, alpha * strength)
        context.fill()
    else:
        context.set_source_rgba(red, green, blue, alpha)
        context.set_line_width(node.stroke or float(spec["spacing"]["stroke"]))
        context.stroke()


def _known() -> set[str]:
    from layout.brand import load_brand
    return set(load_brand())


def _polyline(context, node: Node, alpha: float) -> None:
    if len(node.points) < 2:
        return
    context.move_to(*node.points[0])
    for point in node.points[1:]:
        context.line_to(*point)
    red, green, blue = _unit(colour(node.color))
    context.set_source_rgba(red, green, blue, alpha)
    context.set_line_width(node.stroke or 3)
    context.stroke()


def _bars(context, node: Node, alpha: float, spec: dict) -> None:
    if not node.points:
        return
    width = max(float(spec["spacing"]["s"]), node.rect.w / max(1, len(node.points) * 2))
    red, green, blue = _unit(colour(node.color))
    context.set_source_rgba(red, green, blue, alpha)
    for x, y in node.points:
        context.rectangle(x - width / 2, y, width, node.rect.bottom - y)
        context.fill()


def _connector(context, node: Node, alpha: float) -> None:
    if len(node.points) < 2:
        return
    red, green, blue = _unit(colour("bg_top"))
    context.set_source_rgba(red, green, blue, alpha)
    context.set_line_width(max(node.glow, 4) * 2)
    context.move_to(*node.points[0])
    for point in node.points[1:]:
        context.line_to(*point)
    context.stroke()
    red, green, blue = _unit(colour(node.color))
    context.set_source_rgba(red, green, blue, alpha)
    context.set_line_width(node.stroke or 3)
    context.move_to(*node.points[0])
    for point in node.points[1:]:
        context.line_to(*point)
    context.stroke()


def _paint_text(context, node: Node, alpha: float) -> None:
    raster = text_raster(node)
    _blit(context, raster, node.rect.x, node.rect.y, alpha)


def text_raster(node: Node) -> Image.Image:
    install_fonts()
    font = ImageFont.truetype(str(font_file(node.font_key)), size=int(round(node.font_size)))
    left, top, right, bottom = font.getbbox(node.text)
    width = max(1, int(right - left))
    height = max(1, int(bottom - top))
    raster = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(raster).text(
        (-left, -top), node.text, font=font, fill=_rgb(colour(node.color)) + (255,),
    )
    return raster


def _blit(context, raster: Image.Image, x: float, y: float, alpha: float) -> None:
    arr = np.array(raster)
    if alpha < 0.999:
        arr = arr.copy()
        arr[:, :, 3] = (arr[:, :, 3].astype(np.float32) * alpha).astype(np.uint8)
    height, width = arr.shape[:2]
    premul = np.zeros((height, width, 4), dtype=np.uint8)
    factor = arr[:, :, 3:4].astype(np.float32) / 255.0
    premul[:, :, 0] = (arr[:, :, 2] * factor[:, :, 0]).astype(np.uint8)
    premul[:, :, 1] = (arr[:, :, 1] * factor[:, :, 0]).astype(np.uint8)
    premul[:, :, 2] = (arr[:, :, 0] * factor[:, :, 0]).astype(np.uint8)
    premul[:, :, 3] = arr[:, :, 3]
    blob = np.ascontiguousarray(premul)
    surface = cairo.ImageSurface.create_for_data(blob, cairo.FORMAT_ARGB32, width, height)
    context.set_source_surface(surface, x, y)
    context.paint()


def _rgb(hex_colour: str) -> tuple[int, int, int]:
    value = hex_colour.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-type]


def _unit(hex_colour: str) -> tuple[float, float, float]:
    return tuple(channel / 255.0 for channel in _rgb(hex_colour))  # type: ignore[return-value]
