"""Map engine for Arkad's Ledger.

Hard rule: geopandas and rasterio are called ONLY from `basemap.py` and
`glow.py`, once per scene, to bake a high-resolution PNG. The per-frame
animation loop imports nothing from here except pure-python path data.
"""
from __future__ import annotations

from pathlib import Path

# geo/ -> src/ -> 2026-10-13/ -> arkads-ledger/
CHANNEL = Path(__file__).resolve().parents[3]
GEO_DIR = CHANNEL / "assets" / "geo"
CACHE = GEO_DIR / "cache"
CACHE.mkdir(parents=True, exist_ok=True)

__all__ = ["projections", "natural_earth", "glow", "basemap", "camera",
           "choropleth", "routes", "CHANNEL", "GEO_DIR", "CACHE"]