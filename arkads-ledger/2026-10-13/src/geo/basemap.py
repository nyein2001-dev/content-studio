"""Base map baking.

ONE call per scene produces ONE high-resolution PNG. The frame loop then only
crops and animates that PNG, so geopandas never runs per frame.

Draw order matches the reference look: land, borders, coastline, rivers,
glow, then city dots.
"""
from __future__ import annotations

import functools
import math
from pathlib import Path

import cairo
import numpy as np

from . import glow as glowmod
from . import natural_earth as ne
from . import projections

MAX_LONG_SIDE = 6000
ZOOM_HEADROOM = 1.5          # bake at 1.5x the maximum camera zoom

try:                                    # the channel owns the palette
    import theme as _T

    LAND = _T.PILL_EDGE if False else "#22467F"
    LAND_ALT = "#2A5394"
    BORDER = _T.IVORY
    COAST = "#8FA6D6"
    RIVER = _T.BLUE
except Exception:                       # pragma: no cover - theme is always present
    LAND, LAND_ALT = "#22467F", "#2A5394"
    BORDER, COAST, RIVER = "#F2EBD8", "#8FA6D6", "#4A8FE0"
GLOW_ALPHA = 0.92


def _hex(c: str) -> tuple[float, float, float]:
    c = c.lstrip("#")
    return (int(c[0:2], 16) / 255.0, int(c[2:4], 16) / 255.0, int(c[4:6], 16) / 255.0)


def _fit(extent, width: int, height: int):
    """Return a callable lon/lat or projected -> pixel, plus the inverse."""
    minx, miny, maxx, maxy = extent
    spanx = max(1e-9, maxx - minx)
    spany = max(1e-9, maxy - miny)
    scale = min(width / spanx, height / spany)
    ox = (width - spanx * scale) / 2.0
    oy = (height - spany * scale) / 2.0

    def to_px(x, y):
        return ((x - minx) * scale + ox, (height - (y - miny) * scale) - oy)

    # The offsets matter: Equal Earth is about 2:1 while a Shorts frame is 9:16,
    # so a world bake is letterboxed heavily and the camera must know by how much.
    return to_px, scale, (minx, miny, maxx, maxy), (ox, oy)


def _path(cr: cairo.Context, geom, to_px) -> None:
    gtype = geom.geom_type
    if gtype == "Polygon":
        _path(cr, geom.exterior, to_px)
        for r in geom.interiors:
            _path(cr, r, to_px)
    elif gtype == "MultiPolygon":
        for p in geom.geoms:
            _path(cr, p, to_px)
    elif gtype in ("LineString", "LinearRing"):
        # LinearRing is what a polygon's exterior/interior actually is, so it
        # must be handled here or every country traces an empty path.
        xs, ys = geom.xy
        pts = [to_px(x, y) for x, y in zip(xs, ys)]
        if len(pts) < 2:
            return
        cr.move_to(*pts[0])
        for p in pts[1:]:
            cr.line_to(*p)
        if gtype == "LinearRing":
            cr.close_path()
    elif gtype == "MultiLineString":
        for g in geom.geoms:
            _path(cr, g, to_px)
    elif gtype == "GeometryCollection":
        for g in geom.geoms:
            _path(cr, g, to_px)
    elif gtype == "Point":
        px, py = to_px(geom.x, geom.y)
        cr.move_to(px, py)
        cr.line_to(px + 0.01, py + 0.01)
    elif gtype == "MultiPoint":
        for g in geom.geoms:
            _path(cr, g, to_px)


@functools.lru_cache(maxsize=1)
def projected(layer: str, crs_srs: str):
    """Project one Natural Earth layer into an equal-area CRS, once."""
    gdf = ne.gdf_safe(layer).to_crs(crs_srs)
    return gdf


def rivers_in(crs, limit: int = 40):
    """Projected river polylines, for the doctor and for route overlays."""
    gdf = projected("rivers", crs.srs)
    out = []
    t = projections.transformer("EPSG:4326", crs.srs)
    for geom in list(gdf.geometry)[:limit * 4]:
        for line in getattr(geom, "geoms", [geom]):
            try:
                xs, ys = line.xy
            except Exception:
                continue
            pts = _line_in(np.asarray(xs), np.asarray(ys), t)
            if pts:
                out.append(pts)
            if len(out) >= limit:
                return out
    return out


def _line_in(lon, lat, t):
    xs, ys = t.transform(list(lon), list(lat))
    pts = [(float(a), float(b)) for a, b in zip(xs, ys) if math.isfinite(a) and math.isfinite(b)]
    return pts if len(pts) >= 2 else None


def world_png(out: Path, width: int = 900, crs=None, glow_source: dict | None = None,
              height: int | None = None, max_zoom: float = 1.0,
              city_min_pop: int = 0, extent: tuple | None = None) -> Path:
    """Bake a world (or region) base map to a PNG."""
    import pyproj

    crs = crs or projections.world_equal_area()
    if not projections.is_equal_area(crs):
        raise ValueError(f"base maps must be equal-area; got {crs.name}")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)

    width = int(width)
    height = int(height or round(width * 1920 / 1080))
    # bake at 1.5x the closest camera zoom, capped at 6000 px on the long side
    bake_long = max(2, int(round(max(width, height) * max(1.0, max_zoom) * ZOOM_HEADROOM)))
    long_side = min(MAX_LONG_SIDE, bake_long)
    if width >= height:
        W, H = long_side, max(2, int(round(long_side * height / width)))
    else:
        H, W = long_side, max(2, int(round(long_side * width / height)))

    countries = projected("countries", crs.srs)
    if extent is None:
        b = countries.total_bounds
        extent = (float(b[0]), float(b[1]), float(b[2]), float(b[3]))
    to_px, scale, _, offset = _fit(extent, W, H)

    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    cr = cairo.Context(surf)

    # ocean / page
    g = cairo.LinearGradient(0, 0, 0, H)
    g.add_color_stop_rgba(0.0, *_hex("#061634"), 1.0)
    g.add_color_stop_rgba(0.55, *_hex("#04102A"), 1.0)
    g.add_color_stop_rgba(1.0, *_hex("#020A1C"), 1.0)
    cr.set_source(g)
    cr.paint()

    # land, two tones for a hint of structure
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    for i, geom in enumerate(countries.geometry):
        if geom is None or geom.is_empty:
            continue
        cr.new_sub_path()
        _path(cr, geom, to_px)
        cr.set_source_rgba(*_hex(LAND if i % 2 == 0 else LAND_ALT), 1.0)
        cr.fill()

    # glow, on top of the land
    src = glow_source or glowmod.current()
    tile = glowmod.make_layer(src, GEO_CACHE, (H, W), extent, crs.srs)
    _blit_rgba(cr, tile, 0, 0)

    # rivers
    riv = projected("rivers", crs.srs)
    cr.set_source_rgba(*_hex(RIVER), 0.85)
    for geom in riv.geometry:
        if geom is None or geom.is_empty:
            continue
        cr.new_sub_path()
        _path(cr, geom, to_px)
        cr.set_line_width(max(0.7, 1.6 * ZOOM_HEADROOM * 0.5))
        cr.stroke()

    # thin borders, low-opacity ivory (Natural Earth defaults, no commentary)
    bor = projected("borderlines", crs.srs)
    cr.set_source_rgba(*_hex(BORDER), 0.30)
    cr.set_line_width(max(0.6, 1.1 * 0.5))
    for geom in bor.geometry:
        if geom is None or geom.is_empty:
            continue
        cr.new_sub_path()
        _path(cr, geom, to_px)
        cr.stroke()

    # coastline on top of everything geographic
    co = projected("coastline", crs.srs)
    cr.set_source_rgba(*_hex(COAST), 0.70)
    cr.set_line_width(max(0.8, 1.8 * 0.5))
    for geom in co.geometry:
        if geom is None or geom.is_empty:
            continue
        cr.new_sub_path()
        _path(cr, geom, to_px)
        cr.stroke()

    # lakes as darker voids so they read as water
    try:
        lk = projected("lakes", crs.srs)
        cr.set_source_rgba(*_hex("#04102A"), 0.95)
        for geom in lk.geometry:
            if geom is None or geom.is_empty:
                continue
            cr.new_sub_path()
            _path(cr, geom, to_px)
            cr.fill()
    except Exception:
        pass

    # city dots, only where the story needs them
    if city_min_pop > 0:
        t = projections.transformer("EPSG:4326", crs.srs)
        r = max(1.2, 3.0 * 0.5)
        for c in ne.major_places(city_min_pop):
            xs, ys = t.transform(c["lon"], c["lat"])
            px, py = to_px(xs, ys)
            if 0 <= px < W and 0 <= py < H:
                cr.set_source_rgba(*_hex("#CFE0FF"), 0.72)
                cr.arc(px, py, r, 0, 6.2832)
                cr.fill()

    surf.flush()
    surf.write_to_png(str(out))
    meta = {"width": W, "height": H, "crs": crs.srs, "crs_name": crs.name,
            "scale": scale, "extent": list(extent), "offset": list(offset),
            "glow": src.get("source"),
            "equal_area": projections.is_equal_area(crs)}
    out.with_suffix(".json").write_text(__import__("json").dumps(meta, indent=2),
                                        encoding="utf-8")
    return out


from . import CACHE as GEO_CACHE


def _blit_rgba(cr: cairo.Context, tile: np.ndarray, x: int, y: int) -> None:
    """Composite an RGBA float32 tile (0..1) onto the context."""
    if tile is None or tile.size == 0:
        return
    h, w = tile.shape[:2]
    a = np.clip(tile[..., 3] * GLOW_ALPHA, 0, 1)
    buf = np.zeros((h, w, 4), dtype=np.uint8)
    for ch in range(3):
        buf[:, :, ch] = (np.clip(tile[:, :, ch], 0, 1) * a * 255).astype(np.uint8)
    buf[:, :, 3] = (a * 255).astype(np.uint8)
    bgra = buf[:, :, [2, 1, 0, 3]].copy()
    s = cairo.ImageSurface.create_for_data(bytearray(bgra.tobytes()), cairo.FORMAT_ARGB32, w, h, w * 4)
    cr.save()
    cr.set_operator(cairo.OPERATOR_OVER)
    cr.set_source_surface(s, x, y)
    cr.paint()
    cr.restore()


def load_baked(png: Path) -> tuple[cairo.ImageSurface, dict]:
    import json

    meta = json.loads(png.with_suffix(".json").read_text(encoding="utf-8"))
    return cairo.ImageSurface.create_from_png(str(png)), meta