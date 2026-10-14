"""Ink metrics. The text engine is the only measurer."""
from __future__ import annotations

from layout.spec import load_spec
from layout.text import GlyphInk, canonical_role, measure

__all__ = ["GlyphInk", "measure", "font_key_for"]


def font_key_for(role: str) -> str:
    spec = load_spec()
    role = canonical_role(role)
    try:
        return spec["type"][role]["font"]
    except KeyError as exc:
        raise KeyError(f"type role {role} is not in layout_spec.yaml") from exc
