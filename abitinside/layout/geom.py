"""Shared geometry. No canvas sizes live here."""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2.0

    @property
    def cy(self) -> float:
        return self.y + self.h / 2.0

    def contains(self, other: "Rect", eps: float = 0.51) -> bool:
        return (
            other.x >= self.x - eps
            and other.y >= self.y - eps
            and other.right <= self.right + eps
            and other.bottom <= self.bottom + eps
        )

    def intersects(self, other: "Rect", eps: float = 0.0) -> bool:
        return not (
            other.right <= self.x + eps
            or self.right <= other.x + eps
            or other.bottom <= self.y + eps
            or self.bottom <= other.y + eps
        )

    def gap(self, other: "Rect") -> float:
        """Positive separation. Zero when the rectangles meet or overlap."""
        dx = max(other.x - self.right, self.x - other.right, 0.0)
        dy = max(other.y - self.bottom, self.y - other.bottom, 0.0)
        if dx and dy:
            return math.hypot(dx, dy)
        return dx + dy

    def inflate(self, pad: float) -> "Rect":
        return Rect(self.x - pad, self.y - pad, self.w + 2 * pad, self.h + 2 * pad)

    def union(self, other: "Rect") -> "Rect":
        x = min(self.x, other.x)
        y = min(self.y, other.y)
        return Rect(x, y, max(self.right, other.right) - x, max(self.bottom, other.bottom) - y)


def snap(value: float, grid: int) -> int:
    return int(round(value / grid) * grid)


def segment_hits_rect(x0: float, y0: float, x1: float, y1: float, rect: Rect, pad: float = 0.0) -> bool:
    """True when a segment comes within `pad` of the rectangle interior."""
    box = rect.inflate(pad)
    if _point_in(x0, y0, box) or _point_in(x1, y1, box):
        return True
    edges = (
        (box.x, box.y, box.right, box.y),
        (box.right, box.y, box.right, box.bottom),
        (box.right, box.bottom, box.x, box.bottom),
        (box.x, box.bottom, box.x, box.y),
    )
    return any(_segments_cross(x0, y0, x1, y1, *edge) for edge in edges)


def _point_in(x: float, y: float, rect: Rect) -> bool:
    return rect.x <= x <= rect.right and rect.y <= y <= rect.bottom


def _segments_cross(ax, ay, bx, by, cx, cy, dx, dy) -> bool:
    def cross(px, py, qx, qy, rx, ry) -> float:
        return (qx - px) * (ry - py) - (qy - py) * (rx - px)

    d1 = cross(cx, cy, dx, dy, ax, ay)
    d2 = cross(cx, cy, dx, dy, bx, by)
    d3 = cross(ax, ay, bx, by, cx, cy)
    d4 = cross(ax, ay, bx, by, dx, dy)
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True
    return False
