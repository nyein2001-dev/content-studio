"""Brand colours and font files. Sizes are not read from the episode theme."""
from __future__ import annotations

import importlib.util
from functools import lru_cache

from layout.spec import ABIT, load_spec

_THEME_KEYS = {
    "bg_top": "BG_TOP",
    "bg_bottom": "BG_BOTTOM",
    "bg_corner": "BG_CORNER",
    "ink": "INK",
    "ink_dim": "INK_DIM",
    "ink_faint": "INK_FAINT",
    "cyan": "CYAN",
    "yellow": "YELLOW",
    "coral": "CORAL",
    "green": "GREEN",
    "glow": "GLOW",
}


class BrandError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def load_brand() -> dict[str, str]:
    spec = load_spec()
    theme_path = ABIT / "2026-10-13" / "src" / "theme.py"
    if not theme_path.is_file():
        raise BrandError(f"brand theme is missing at {theme_path}")
    module_spec = importlib.util.spec_from_file_location("abitinside_episode_theme", theme_path)
    if module_spec is None or module_spec.loader is None:
        raise BrandError("could not load the episode theme module")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    colours = {}
    for token, attr in _THEME_KEYS.items():
        value = getattr(module, attr, None)
        if not isinstance(value, str) or not value.startswith("#"):
            raise BrandError(f"theme.{attr} is not a hex colour")
        colours[token] = value
    unknown = [name for name in spec["brand_tokens"] if name not in colours]
    if unknown:
        raise BrandError(f"spec brand tokens missing from theme: {unknown}")
    return colours


def colour(token: str) -> str:
    brand = load_brand()
    if token not in brand:
        raise BrandError(
            f"colour {token!r} is not a theme token. "
            f"Use one of: {', '.join(sorted(brand))}."
        )
    return brand[token]
