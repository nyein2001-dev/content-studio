"""Natural Earth 10m loading.

Everything expensive happens here, once, at bake time. The frame loop never
imports geopandas.
"""
from __future__ import annotations

import functools
from pathlib import Path

from . import GEO_DIR

GEO = GEO_DIR
LAYERS = ("countries", "borderlines", "coastline", "rivers", "places", "lakes")

# Logical layer name -> the shapefile basename inside the downloaded archive.
SHAPEFILE = {
    "countries": "ne_10m_admin_0_countries",
    "borderlines": "ne_10m_admin_0_boundary_lines_land",
    "coastline": "ne_10m_coastline",
    "rivers": "ne_10m_rivers_lake_centerlines",
    "places": "ne_10m_populated_places",
    "lakes": "ne_10m_lakes",
}


def path_for(layer: str) -> Path:
    p = GEO / f"{SHAPEFILE[layer]}.shp"
    if not p.is_file():
        raise FileNotFoundError(f"Natural Earth layer {layer!r} not found at {p}")
    return p


@functools.lru_cache(maxsize=1)
def countries():
    import geopandas as gpd

    gdf = gpd.read_file(path_for("countries"))
    return gdf


@functools.lru_cache(maxsize=1)
def country_code_columns() -> dict:
    """The robust join codes. ISO_A3 is -99 for several countries, so never use it."""
    gdf = countries()
    return {"ADM0_A3": "ADM0_A3" in gdf.columns,
            "ISO_A3_EH": "ISO_A3_EH" in gdf.columns,
            "SOV_A3": "SOV_A3" in gdf.columns}


@functools.lru_cache(maxsize=1)
def borders():
    import geopandas as gpd

    return gdf_safe("borderlines")


def gdf_safe(layer: str):
    import geopandas as gpd

    return gpd.read_file(path_for(layer))


@functools.lru_cache(maxsize=1)
def rivers():
    import geopandas as gpd

    gdf = gpd.read_file(path_for("rivers"))
    # keep only named, non-minor rivers: at 10m the file carries 243k features
    if "name" in gdf.columns:
        gdf = gdf[~gdf["name"].isna() & (gdf["name"].astype(str).str.len() > 2)]
    if "scalerank" in gdf.columns:
        gdf = gdf[gdf["scalerank"].astype(float) <= 6]
    return gdf.head(4000)


@functools.lru_cache(maxsize=1)
def places():
    import geopandas as gpd

    gdf = gpd.read_file(path_for("places"))
    for c in ("POP_MAX", "POP_MIN"):
        if c in gdf.columns:
            gdf[c] = gdf[c].fillna(0.0)
    return gdf


@functools.lru_cache(maxsize=1)
def lakes():
    import geopandas as gpd

    return gpd.read_file(path_for("lakes"))


def major_places(min_pop: int = 400_000) -> list[dict]:
    """City dots, only where the story needs them."""
    gdf = places()
    col = "POP_MAX" if "POP_MAX" in gdf.columns else "POP_MIN"
    gdf = gdf[gdf[col] >= min_pop]
    name_col = next((c for c in ("NAME", "NAMEASCII", "NAMEPAR", "CITYNAME")
                     if c in gdf.columns), None)
    out = []
    for _, r in gdf.iterrows():
        geom = r.geometry
        if geom is None or geom.is_empty:
            continue
        pt = geom.representative_point()
        out.append({"name": str(r.get(name_col, "")) if name_col else "",
                    "lon": float(pt.x), "lat": float(pt.y), "pop": float(r[col]),
                    "adm0": str(r.get("ADM0NAME", ""))})
    out.sort(key=lambda d: -d["pop"])
    return out


def named_rivers(min_scale: int = 4) -> list[dict]:
    gdf = rivers()
    out = []
    for _, r in gdf.iterrows():
        out.append({"name": str(r.get("name", "")), "scalerk": int(r.get("scalerank", 9))})
    return out


def unmatched_codes(gdf, codes: list[str], key: str = "ADM0_A3") -> list[str]:
    have = set(gdf[key].astype(str)) if key in gdf.columns else set()
    return sorted({c for c in codes if str(c) not in have})