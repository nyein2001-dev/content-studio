"""Fit ladder. Never truncates, ellipsizes, or hyphenates."""
from __future__ import annotations

from dataclasses import dataclass

from layout.errors import LayoutError
from layout.metrics import GlyphInk, font_key_for, measure
from layout.spec import load_spec
from layout.text import canonical_role, wrap


@dataclass(frozen=True)
class FittedText:
    lines: tuple[str, ...]
    size: float
    role: str
    font_key: str
    inks: tuple[GlyphInk, ...]
    width: float
    height: float
    line_gap: float


def _wrap(text: str, font_key: str, size: float, max_width: float, max_lines: int) -> tuple[str, ...] | None:
    return wrap(text, font_key, size, max_width, max_lines)


def try_fit(text: str, role: str, max_width: float, size: float, max_lines: int | None = None) -> FittedText | None:
    spec = load_spec()
    role = canonical_role(role)
    role_spec = spec["type"][role]
    font_key = font_key_for(role)
    gap = float(spec["spacing"]["line_gap"])
    limit = role_spec["max_lines"] if max_lines is None else min(max_lines, role_spec["max_lines"])
    if "\n" not in text:
        single = measure(text, font_key, size)
        if max(single.width, single.advance) <= max_width:
            return _pack(text, (text,), size, role, font_key, gap)
    wrapped = _wrap(text, font_key, size, max_width, limit)
    if wrapped is None:
        return None
    return _pack(text, wrapped, size, role, font_key, gap)


def fit_text(
    scene: str,
    text: str,
    role: str,
    max_width: float,
    max_lines: int | None = None,
    allow_shrink: bool = True,
) -> FittedText:
    spec = load_spec()
    role = canonical_role(role)
    role_spec = spec["type"][role]
    step = int(spec["spacing"]["shrink_step"])
    size = int(role_spec["preferred"])
    floor = int(role_spec["floor"])
    if not allow_shrink:
        fitted = try_fit(text, role, max_width, size, max_lines)
        if fitted is None:
            raise LayoutError(
                scene, "R09",
                f"{role} text {text!r} does not fit in {max_width:.0f}px at {size}px",
                "Shorten this wording in the scene DSL. The engine will not cut or rewrite the words.",
                role=role, max_width=max_width, size=size,
            )
        return fitted
    if (size - floor) % step != 0:
        size = size - ((size - floor) % step)
    while size >= floor:
        fitted = try_fit(text, role, max_width, size, max_lines)
        if fitted is not None:
            return fitted
        if size == floor:
            break
        size = max(floor, size - step)
    raise LayoutError(
        scene, "R09",
        f"{role} text {text!r} does not fit in {max_width:.0f}px even at {floor}px and {role_spec['max_lines']} lines",
        "Shorten this wording in the scene DSL, or remove a neighboring component so the slot can widen. "
        "The engine will not cut, ellipsize, or rewrite the words.",
        role=role, max_width=max_width, floor=floor,
    )


def _pack(text: str, lines: tuple[str, ...], size: float, role: str, font_key: str, gap: float) -> FittedText:
    inks = tuple(measure(line, font_key, size) for line in lines)
    width = max(max(ink.width, ink.advance) for ink in inks)
    height = sum(ink.height for ink in inks) + gap * (len(inks) - 1)
    return FittedText(lines, float(size), role, font_key, inks, width, height, gap)
