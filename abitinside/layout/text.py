"""The only module allowed to measure or draw text.

Measurement and drawing share one Pango layout, so the ink box equals the
rendered ink. The bundled font files are the only faces. System fallback is
a hard failure.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass

from layout.errors import LayoutError
from layout.fonts import font_file, install_fonts
from layout.spec import ABIT, load_spec

PANGO_SCALE = 1024
CAIRO_FORMAT_ARGB32 = 0

FAMILY = {
    "bold": "ABit Bold",
    "semibold": "ABit SemiBold",
    "regular": "ABit Regular",
    "mono": "ABit Mono",
}


class _Rect(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("width", ctypes.c_int),
        ("height", ctypes.c_int),
    ]


_LIBS = None


def _library_paths() -> dict[str, str]:
    """Bundled micromamba libs, then the system pangocairo. Never a toy font."""
    import ctypes.util

    lib = ABIT / "tools" / "cdeps" / "lib"
    bundled = {
        "cairo": lib / "libcairo.so.2",
        "pango": lib / "libpango-1.0.so.0",
        "pangocairo": lib / "libpangocairo-1.0.so.0",
        "gobject": lib / "libgobject-2.0.so.0",
    }
    if all(path.is_file() for path in bundled.values()):
        return {key: str(path) for key, path in bundled.items()}
    found = {
        "cairo": ctypes.util.find_library("cairo"),
        "pango": ctypes.util.find_library("pango-1.0"),
        "pangocairo": ctypes.util.find_library("pangocairo-1.0"),
        "gobject": ctypes.util.find_library("gobject-2.0"),
    }
    if all(found.values()):
        return {key: str(path) for key, path in found.items()}
    raise LayoutError(
        "fonts",
        "R09",
        "pangocairo is not available",
        "Install cairo, pango, and PyGObject with bash setup.sh "
        "(micromamba install -c conda-forge cairo pango pygobject, then uv pip install PyGObject). "
        "The build will not fall back to toy fonts or Pillow.",
    )


def canonical_role(role: str) -> str:
    return {
        "headline": "title",
        "caption": "subtitle",
        "footnote": "badge",
        "body": "stage",
        "card_title": "stage",
    }.get(role, role)


@dataclass(frozen=True)
class GlyphInk:
    width: float
    height: float
    bearing_x: float
    bearing_y: float
    advance: float


def _load_libs():
    global _LIBS
    if _LIBS is not None:
        return _LIBS
    names = _library_paths()
    cairo = ctypes.CDLL(names["cairo"])
    pango = ctypes.CDLL(names["pango"])
    pangocairo = ctypes.CDLL(names["pangocairo"])
    gobject = ctypes.CDLL(names["gobject"])
    cairo.cairo_image_surface_create.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
    cairo.cairo_image_surface_create.restype = ctypes.c_void_p
    cairo.cairo_create.argtypes = [ctypes.c_void_p]
    cairo.cairo_create.restype = ctypes.c_void_p
    cairo.cairo_destroy.argtypes = [ctypes.c_void_p]
    cairo.cairo_surface_destroy.argtypes = [ctypes.c_void_p]
    cairo.cairo_surface_flush.argtypes = [ctypes.c_void_p]
    cairo.cairo_translate.argtypes = [ctypes.c_void_p, ctypes.c_double, ctypes.c_double]
    cairo.cairo_set_source_rgba.argtypes = [
        ctypes.c_void_p, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double,
    ]
    cairo.cairo_image_surface_get_data.argtypes = [ctypes.c_void_p]
    cairo.cairo_image_surface_get_data.restype = ctypes.POINTER(ctypes.c_ubyte)
    cairo.cairo_image_surface_get_stride.argtypes = [ctypes.c_void_p]
    cairo.cairo_image_surface_get_stride.restype = ctypes.c_int
    pango.pango_font_description_from_string.argtypes = [ctypes.c_char_p]
    pango.pango_font_description_from_string.restype = ctypes.c_void_p
    pango.pango_font_description_set_absolute_size.argtypes = [ctypes.c_void_p, ctypes.c_double]
    pango.pango_font_description_free.argtypes = [ctypes.c_void_p]
    pango.pango_layout_set_font_description.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    pango.pango_layout_set_text.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    pango.pango_layout_get_pixel_extents.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(_Rect), ctypes.POINTER(_Rect),
    ]
    pangocairo.pango_cairo_create_layout.argtypes = [ctypes.c_void_p]
    pangocairo.pango_cairo_create_layout.restype = ctypes.c_void_p
    pangocairo.pango_cairo_show_layout.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    pangocairo.pango_cairo_update_layout.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    gobject.g_object_unref.argtypes = [ctypes.c_void_p]
    _LIBS = (cairo, pango, pangocairo, gobject)
    return _LIBS


def _description(font_key: str, size: float):
    _, pango, _, _ = _load_libs()
    font_file(font_key)
    family = FAMILY[font_key]
    desc = pango.pango_font_description_from_string(family.encode())
    pango.pango_font_description_set_absolute_size(desc, float(size) * PANGO_SCALE)
    return desc


def _extents(text: str, font_key: str, size: float) -> tuple[_Rect, _Rect]:
    install_fonts()
    cairo, pango, pangocairo, gobject = _load_libs()
    surface = cairo.cairo_image_surface_create(CAIRO_FORMAT_ARGB32, 8, 8)
    context = cairo.cairo_create(surface)
    layout = pangocairo.pango_cairo_create_layout(context)
    desc = _description(font_key, size)
    pango.pango_layout_set_font_description(layout, desc)
    raw = (text or "").encode()
    pango.pango_layout_set_text(layout, raw, len(raw))
    pangocairo.pango_cairo_update_layout(context, layout)
    ink = _Rect()
    logical = _Rect()
    pango.pango_layout_get_pixel_extents(layout, ctypes.byref(ink), ctypes.byref(logical))
    pango.pango_font_description_free(desc)
    gobject.g_object_unref(layout)
    cairo.cairo_destroy(context)
    cairo.cairo_surface_destroy(surface)
    return ink, logical


def measure(text: str, font_key: str, size: float) -> GlyphInk:
    if text == "":
        return GlyphInk(0.0, 0.0, 0.0, 0.0, 0.0)
    ink, logical = _extents(text, font_key, size)
    return GlyphInk(
        width=float(max(ink.width, 0)),
        height=float(max(ink.height, 1)),
        bearing_x=float(ink.x),
        bearing_y=float(ink.y),
        advance=float(logical.width),
    )


def wrap(text: str, font_key: str, size: float, max_width: float, max_lines: int) -> tuple[str, ...] | None:
    if "\n" in text:
        lines = tuple(text.split("\n"))
        if len(lines) > max_lines or not lines:
            return None
        for line in lines:
            ink = measure(line, font_key, size)
            if max(ink.width, ink.advance) > max_width:
                return None
        return lines
    words = text.split()
    if not words:
        return None
    lines: list[str] = []
    current = ""
    for word in words:
        ink = measure(word, font_key, size)
        if max(ink.width, ink.advance) > max_width:
            return None
        trial = word if not current else f"{current} {word}"
        trial_ink = measure(trial, font_key, size)
        if max(trial_ink.width, trial_ink.advance) <= max_width:
            current = trial
            continue
        if not current:
            return None
        lines.append(current)
        current = word
        if len(lines) >= max_lines:
            return None
    if current:
        lines.append(current)
    if len(lines) > max_lines or not lines:
        return None
    return tuple(lines)


def _paint(text: str, font_key: str, size: float, color_rgb: tuple[float, float, float]):
    """Return ink and an RGBA image of that ink. One Pango layout paints it."""
    import numpy as np
    from PIL import Image

    install_fonts()
    ink_box = measure(text, font_key, size)
    width = max(1, int(round(ink_box.width)))
    height = max(1, int(round(ink_box.height)))
    cairo, pango, pangocairo, gobject = _load_libs()
    surface = cairo.cairo_image_surface_create(CAIRO_FORMAT_ARGB32, width, height)
    context = cairo.cairo_create(surface)
    cairo.cairo_translate(context, -ink_box.bearing_x, -ink_box.bearing_y)
    cairo.cairo_set_source_rgba(context, *color_rgb, 1.0)
    layout = pangocairo.pango_cairo_create_layout(context)
    desc = _description(font_key, size)
    pango.pango_layout_set_font_description(layout, desc)
    raw = text.encode()
    pango.pango_layout_set_text(layout, raw, len(raw))
    pangocairo.pango_cairo_update_layout(context, layout)
    pangocairo.pango_cairo_show_layout(context, layout)
    cairo.cairo_surface_flush(surface)
    stride = cairo.cairo_image_surface_get_stride(surface)
    pointer = cairo.cairo_image_surface_get_data(surface)
    buf = np.ctypeslib.as_array(pointer, shape=(height, stride // 4, 4)).copy()
    bgra = buf[:, :width, :]
    rgba = np.empty((height, width, 4), dtype=np.uint8)
    rgba[:, :, 0] = bgra[:, :, 2]
    rgba[:, :, 1] = bgra[:, :, 1]
    rgba[:, :, 2] = bgra[:, :, 0]
    rgba[:, :, 3] = bgra[:, :, 3]
    image = Image.fromarray(rgba, "RGBA")
    pango.pango_font_description_free(desc)
    gobject.g_object_unref(layout)
    cairo.cairo_destroy(context)
    cairo.cairo_surface_destroy(surface)
    return ink_box, image


def draw(context, text: str, font_key: str, size: float, color_rgb: tuple[float, float, float], alpha: float = 1.0) -> None:
    import cairo
    import numpy as np

    _ink, image = _paint(text, font_key, size, color_rgb)
    arr = np.array(image)
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
    context.set_source_surface(surface, 0, 0)
    context.paint()


def raster(text: str, font_key: str, size: float, color_rgb: tuple[int, int, int]):
    _ink, image = _paint(text, font_key, size, tuple(channel / 255.0 for channel in color_rgb))
    return image
