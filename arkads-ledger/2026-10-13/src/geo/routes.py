"""Routes: great-circle arcs drawn progressively by path length.

The path is projected once at bake time. Every frame the renderer asks for the
prefix of the path that corresponds to the current progress, so the draw is
linear in time and never re-projects.
"""
from __future__ import annotations

import cairo
import numpy as np

from . import projections


def arc(a: tuple[float, float], b: tuple[float, float], crs_srs: str,
        n: int = 64, lift: float = 0.10) -> list[tuple[float, float]]:
    """Great-circle arc between two lon/lat points, projected into the CRS.

    `lift` raises the midpoint so the arc reads as a flight path rather than a
    flat line; 0 gives the ground path.
    """
    t = projections.transformer("EPSG:4326", crs_srs)
    pts = projections.geodesic_to([a, b], t, n)[0]
    if lift <= 0:
        return [(float(x), float(y)) for x, y in pts]
    ax, ay = pts[0]
    bx, by = pts[-1]
    out = []
    for i, (x, y) in enumerate(pts):
        u = i / max(1, len(pts) - 1)
        w = float(np.sin(np.pi * u)) * lift
        out.append((float(x + (bx - ax) * w * 0.55), float(y + (by - ay) * w)))
    return out


def cumulative_lengths(path: list[tuple[float, float]]) -> list[float]:
    acc = [0.0]
    for i in range(1, len(path)):
        acc.append(acc[-1] + float(np.hypot(path[i][0] - path[i - 1][0],
                                            path[i][1] - path[i - 1][1])))
    return acc


def prefix(path: list[tuple[float, float]], progress: float,
           lengths: list[float] | None = None) -> list[tuple[float, float]]:
    """The portion of `path` drawn at `progress` (0..1), by arc length."""
    if progress <= 0:
        return []
    if progress >= 1:
        return list(path)
    if lengths is None:
        lengths = cumulative_lengths(path)
    total = lengths[-1]
    if total <= 0:
        return list(path)
    target = total * progress
    out = [path[0]]
    for i in range(1, len(path)):
        if lengths[i] >= target:
            lo, hi = lengths[i - 1], lengths[i]
            t = 0.0 if hi <= lo else (target - lo) / (hi - lo)
            x0, y0 = path[i - 1]
            x1, y1 = path[i]
            out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
            break
        out.append(path[i])
    return out


def draw_path(cr: cairo.Context, cam, path: list[tuple[float, float]], view,
              progress: float = 1.0, colour=(0.91, 0.65, 0.16), width: float = 6.0,
              glow: bool = True, lengths=None) -> None:
    pts = prefix(path, progress, lengths)
    if len(pts) < 2:
        return
    screen = [cam.to_screen(p, view) for p in pts]
    if glow:
        cr.set_source_rgba(colour[0], colour[1], colour[2], 0.22)
        cr.set_line_width(width * 2.6)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.move_to(*screen[0])
        for p in screen[1:]:
            cr.line_to(*p)
        cr.stroke()
    cr.set_source_rgba(colour[0], colour[1], colour[2], 1.0)
    cr.set_line_width(width)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.move_to(*screen[0])
    for p in screen[1:]:
        cr.line_to(*p)
    cr.stroke()
    cr.set_line_cap(cairo.LINE_CAP_BUTT)


def head(cam, path: list[tuple[float, float]], view, progress: float,
         lengths=None):
    """Screen position of the moving draw head, or None before it starts."""
    pts = prefix(path, progress, lengths)
    return cam.to_screen(pts[-1], view) if pts else None