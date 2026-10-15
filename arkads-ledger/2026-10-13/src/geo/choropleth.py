"""Choropleth: a single-hue sequential ramp, navy -> gold, colour-blind safe.

Countries are joined on ADM0_A3 (or ISO_A3_EH), never on ISO_A3, which Natural
Earth fills with -99 for several countries. Unmatched codes are returned so
they can be listed in qa-report.md instead of silently dropping a country.
"""
from __future__ import annotations

import functools

import cairo

from . import natural_earth as ne
from . import projections

NAVY = (0.043, 0.086, 0.216)
GOLD = (0.910, 0.651, 0.157)
MID = (0.38, 0.36, 0.42)


def ramp(v: float) -> tuple[float, float, float]:
    """A monotone navy -> gold ramp. Perceptually ordered, safe for the common
    red-green colour deficiencies because it changes in lightness, not hue only."""
    v = 0.0 if v < 0 else (1.0 if v > 1 else v)
    t = v ** 0.82
    return tuple(NAVY[i] + (GOLD[i] - NAVY[i]) * t for i in range(3))


def join(values: dict[str, float], key: str = "ADM0_A3") -> tuple[dict[str, float], list[str]]:
    gdf = ne.countries()
    col = key if key in gdf.columns else ("ISO_A3_EH" if "ISO_A3_EH" in gdf.columns else "ADM0_A3")
    have = {}
    for _, r in gdf.iterrows():
        have[str(r[col])] = None
    matched = {c: v for c, v in values.items() if c in have}
    unmatched = sorted(c for c in values if c not in have)
    return matched, unmatched


def normalise(values: dict[str, float]) -> dict[str, float]:
    """Min-max to 0..1 across the matched set only."""
    if not values:
        return {}
    lo, hi = min(values.values()), max(values.values())
    if hi - lo < 1e-12:
        return {k: 0.5 for k in values}
    return {k: (v - lo) / (hi - lo) for k, v in values.items()}


@functools.lru_cache(maxsize=4)
def country_shapes(crs_srs: str):
    """Projected country polygons keyed by ADM0_A3, baked once per CRS."""
    gdf = ne.countries().to_crs(crs_srs)
    key = "ADM0_A3" if "ADM0_A3" in gdf.columns else "ISO_A3_EH"
    out = {}
    for _, r in gdf.iterrows():
        out[str(r[key])] = r.geometry
    return out


def fill_choropleth(cr: cairo.Context, cam, values: dict[str, float], view,
                    progress: float = 1.0, key: str = "ADM0_A3") -> tuple[int, list[str]]:
    """Fill countries by value, wiping on as `progress` rises.

    Returns (countries painted, unmatched codes).
    """
    matched, unmatched = join(values, key)
    norm = normalise(matched)
    shapes = country_shapes(cam.crs_srs)
    painted = 0
    order = sorted(norm.items(), key=lambda kv: kv[1])
    total = max(1, len(order))
    for i, (code, v) in enumerate(order):
        if i / total > progress:
            break
        geom = shapes.get(code)
        if geom is None or geom.is_empty:
            continue
        r, g, b = ramp(v)
        cr.set_source_rgba(r, g, b, 0.80)
        _trace(cr, geom, cam, view)
        cr.fill_preserve()
        cr.set_source_rgba(0.95, 0.92, 0.85, 0.16)
        cr.set_line_width(1.4)
        cr.stroke()
        painted += 1
    return painted, unmatched


def _trace(cr: cairo.Context, geom, cam, view) -> None:
    """Trace a projected geometry straight into screen coordinates."""
    from shapely.geometry import MultiPolygon, Polygon

    cr.new_sub_path()
    polys = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    for poly in polys:
        if not isinstance(poly, Polygon):
            continue
        for ring in (poly.exterior, *poly.interiors):
            pts = [cam.to_screen(p, view) for p in ring.coords]
            if len(pts) < 2:
                continue
            cr.move_to(*pts[0])
            for p in pts[1:]:
                cr.line_to(*p)
            cr.close_path()


LEGEND_W = 260
LEGEND_H = 22


def legend(cr, x: float, y: float, title: str, unit: str, data_year: str,
           rgb, draw_text, width: float = LEGEND_W) -> float:
    """Sequential legend with its data year, drawn once per choropleth scene."""
    n = 48
    bw = width / n
    for i in range(n):
        r, g, b = ramp(i / (n - 1))
        cr.set_source_rgba(r, g, b, 1.0)
        cr.rectangle(x + i * bw, y, bw + 0.8, LEGEND_H)
        cr.fill()
    cr.set_source_rgba(*rgb("ivory")[:3], 0.55)
    cr.set_line_width(2)
    cr.rectangle(x, y, width, LEGEND_H)
    cr.stroke()
    yb = y + LEGEND_H + 12
    cr.save()
    cr.translate(x, yb)
    cr.rotate(-1.5708)
    draw_text(cr, 0.0, 0.0, title.upper(), 22, rgb("muted"))
    cr.restore()
    draw_text(cr, x + width, y + LEGEND_H + 10, f"{unit} · {data_year}", 22,
              rgb("ivory"), align="right")
    return y + LEGEND_H + 46