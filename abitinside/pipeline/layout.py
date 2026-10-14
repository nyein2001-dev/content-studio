"""Bounding boxes and the rule for which overlaps are intentional."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Box:
    name: str
    x: float
    y: float
    w: float
    h: float
    role: str
    label_of: str | None = None


def overlaps(a: Box, b: Box) -> bool:
    return not (
        a.x + a.w <= b.x or b.x + b.w <= a.x
        or a.y + a.h <= b.y or b.y + b.h <= a.y
    )


def _approved(a: Box, b: Box) -> bool:
    if a.role == "label" and a.label_of and a.label_of == b.name:
        return True
    if b.role == "label" and b.label_of and b.label_of == a.name:
        return True
    return False


def collisions(boxes: list[Box]) -> list[tuple[str, str]]:
    """Unrelated boxes that intersect. A label attached to its node is allowed."""
    bad: list[tuple[str, str]] = []
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            if _approved(a, b):
                continue
            if overlaps(a, b):
                bad.append((a.name, b.name))
    return bad
