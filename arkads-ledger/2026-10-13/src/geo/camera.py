"""Camera: eased pan and zoom over a baked map PNG.

The baked PNG carries a `scale` (pixels per projected metre) and an `extent`.
A camera state is (centre_x, centre_y, zoom); zoom 1.0 is the full frame. At
most three zoom levels are ever used in a video, so the baked PNG only needs
1.5x the closest one.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import cairo

from videokit import motion

MAX_ZOOM_LEVELS = 3


@dataclass(frozen=True)
class View:
    cx: float
    cy: float
    zoom: float


def _lerp_view(a: View, b: View, t: float) -> View:
    return View(a.cx + (b.cx - a.cx) * t,
                a.cy + (b.cy - a.cy) * t,
                a.zoom * (b.zoom / a.zoom) ** motion.clamp01(t))


def view_at(frame: float, keys: list[tuple[int, int, View]]) -> View:
    """Eased interpolation across a list of (start_frame, end_frame, View)."""
    if not keys:
        return View(0.0, 0.0, 1.0)
    if frame <= keys[0][0]:
        return keys[0][2]
    if frame >= keys[-1][1]:
        return keys[-1][2]
    for i in range(len(keys) - 1):
        s0, e0, v0 = keys[i]
        s1, e1, v1 = keys[i + 1]
        if s0 <= frame <= e0:
            return v0
        if e0 <= frame <= e1:
            t = motion.ease_in_out_cubic(motion.progress(frame, e0, e1))
            return _lerp_view(v0, v1, t)
    return keys[-1][2]


class Camera:
    """Composites a baked PNG under an eased view.

    A view centres a projected CRS point (cx, cy) at the middle of the canvas
    and scales the baked image by `zoom`. Everything the frame loop draws is
    projected through the same maths, so pins, routes and callouts stay glued
    to the map while the camera moves.
    """

    def __init__(self, surf: cairo.ImageSurface, meta: dict,
                 canvas: tuple[int, int] = (1080, 1920)):
        self.surf = surf
        self.meta = meta
        self.cw, self.ch = canvas
        self.bake_w, self.bake_h = surf.get_width(), surf.get_height()
        self.scale = float(meta["scale"])
        self.extent = tuple(float(v) for v in meta["extent"])
        self.offset = tuple(float(v) for v in meta.get("offset", (0.0, 0.0)))
        self.crs_srs = meta["crs"]

    # ------------------------------------------------------------------ geometry
    def baked_px(self, xy: tuple[float, float]) -> tuple[float, float]:
        """Projected CRS coordinates -> pixel inside the baked PNG.

        Must reproduce basemap._fit exactly, including the letterbox offsets,
        or the camera centres on the wrong place and shows empty ocean.
        """
        ox, oy = self.offset
        return ((xy[0] - self.extent[0]) * self.scale + ox,
                (self.bake_h - (xy[1] - self.extent[1]) * self.scale) - oy)

    def _anchor(self, v: View) -> tuple[float, float]:
        """Baked-pixel position of the view centre."""
        return self.baked_px((v.cx, v.cy))

    def dest_rect(self, v: View) -> tuple[float, float, float, float]:
        ax, ay = self._anchor(v)
        dx = (0.0 - ax) * v.zoom + self.cw / 2.0
        dy = (0.0 - ay) * v.zoom + self.ch / 2.0
        return dx, dy, self.bake_w * v.zoom, self.bake_h * v.zoom

    def to_screen(self, xy: tuple[float, float], v: View) -> tuple[float, float]:
        px, py = self.baked_px(xy)
        ax, ay = self._anchor(v)
        return ((px - ax) * v.zoom + self.cw / 2.0,
                (py - ay) * v.zoom + self.ch / 2.0)

    def lonlat_to_screen(self, lon: float, lat: float, v: View) -> tuple[float, float]:
        import pyproj

        t = pyproj.Transformer.from_crs("EPSG:4326", self.crs_srs, always_xy=True)
        x, y = t.transform(lon, lat)
        return self.to_screen((float(x), float(y)), v)

    def screen_frac(self, xy: tuple[float, float], v: View) -> tuple[float, float]:
        x, y = self.to_screen(xy, v)
        return (x / self.cw, y / self.ch)

    # ------------------------------------------------------------------ drawing
    def draw(self, cr: cairo.Context, v: View, alpha: float = 1.0) -> None:
        dx, dy, dw, dh = self.dest_rect(v)
        cr.save()
        if alpha >= 0.999:
            cr.set_operator(cairo.OPERATOR_OVER)
            cr.set_source_surface(self.surf, dx, dy)
            cr.paint()
        else:
            cr.push_group()
            cr.set_operator(cairo.OPERATOR_OVER)
            cr.set_source_surface(self.surf, dx, dy)
            cr.paint()
            inner = cr.pop_group()
            cr.set_operator(cairo.OPERATOR_OVER)
            cr.set_source(inner)
            cr.paint_with_alpha(alpha)
        cr.restore()


def zoom_keys(frames_and_views: list[tuple[int, int, float, float, float]]):
    """Build view_at keys from (start, end, cx, cy, zoom) tuples."""
    return [(a, b, View(cx, cy, z)) for a, b, cx, cy, z in frames_and_views]


def assert_zoom_budget(zooms: list[float]) -> None:
    levels = sorted({round(math.log2(max(z, 1e-6)), 1) for z in zooms})
    if len(levels) > MAX_ZOOM_LEVELS:
        raise ValueError(f"camera uses {len(levels)} zoom levels: {levels}")