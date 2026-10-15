"""Glow layer: WorldPop if a no-login download exists, otherwise procedural.

Never blocks the build. If every remote source fails, the procedural branch is
used and the reason is recorded so it can be printed in qa-report.md.

Both branches end at the same place: a log-scaled, percentile-normalised,
multi-scale blurred amber raster of the same shape as the basemap.
"""
from __future__ import annotations

import io
import json
import math
import urllib.request
from pathlib import Path

import numpy as np

from . import CACHE as GEO_CACHE
from . import GEO_DIR

GEO = GEO_DIR
META = GEO / "glow_source.json"

WORLDPOP_INDEX = ("https://data.worldpop.org/GIS/Population/"
                  "Global_2000_2020_Constrained/2020/BSGM/")
VIIRS_INDEX = "https://eogdata.mines.edu/nighttime_light/annual/v22/2018/"
UA = {"User-Agent": "ArkadsLedger/1.0 (educational video production)"}


def record(source: str, **extra) -> dict:
    info = {"source": source, "resolved_utc": None, **extra}
    META.parent.mkdir(parents=True, exist_ok=True)
    META.write_text(json.dumps(info, indent=2), encoding="utf-8")
    return info


def current() -> dict:
    if META.is_file():
        try:
            return json.loads(META.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"source": "procedural", "reason": "not yet resolved"}


# ------------------------------------------------------------------ remote
def _get(url: str, timeout: int = 45) -> bytes | None:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return r.read()
    except Exception:
        return None


def try_worldpop(cache: Path) -> Path | None:
    """Parse the live WorldPop index for a global mosaic and fetch it."""
    cache.mkdir(parents=True, exist_ok=True)
    local = cache / "worldpop.tif"
    if local.is_file() and local.stat().st_size > 100_000:
        return local
    html = _get(WORLDPOP_INDEX)
    if not html:
        return None
    import re

    hrefs = re.findall(rb'href="([^"]+\.zip)"', html)
    pick = None
    for h in hrefs:
        name = h.decode("utf-8", "replace")
        if "Global" in name and "100m" in name:
            pick = name
            break
    if not pick:
        return None
    blob = _get(WORLDPOP_INDEX + pick, timeout=600)
    if not blob:
        return None
    try:
        import zipfile

        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            tif = next(n for n in z.namelist() if n.lower().endswith(".tif"))
            local.write_bytes(z.read(tif))
    except Exception:
        return None
    return local if local.stat().st_size > 100_000 else None


def try_viirs(cache: Path) -> Path | None:
    """VIIRS only if a no-login download exists."""
    cache.mkdir(parents=True, exist_ok=True)
    local = cache / "viirs.tif"
    if local.is_file() and local.stat().st_size > 100_000:
        return local
    for url in (VIIRS_INDEX + "Global_2018_v22_Global_Clip.tif",
                VIIRS_INDEX + "Global_2018_v22_Global.tif"):
        blob = _get(url, timeout=600)
        if blob and len(blob) > 100_000:
            local.write_bytes(blob)
            return local
    return None


# ------------------------------------------------------------------ shaping
def _finalise(raw: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """Log scale -> percentile normalise -> multi-scale blur -> keep it dark.

    The glow must read as sparse lights over a dark map, so the tail is pushed
    down hard and the field is normalised again AFTER blurring. Normalising only
    before the blur is what turns a few bright cities into a solid amber sheet.
    """
    from scipy.ndimage import gaussian_filter, zoom as ndzoom

    h, w = shape
    a = np.asarray(raw, dtype=np.float64)
    a = np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0)
    a = np.clip(a, 0.0, None)
    a = np.log1p(a)
    p = float(np.percentile(a, 99.9))
    if p > 0:
        a = np.clip(a / p, 0.0, 1.0)

    if a.shape != (h, w):
        a = ndzoom(a, (h / a.shape[0], w / a.shape[1]), order=1)
        if a.shape[0] < h:
            a = np.pad(a, ((0, h - a.shape[0]), (0, 0)))
        if a.shape[1] < w:
            a = np.pad(a, ((0, 0), (0, w - a.shape[1])))
        a = a[:h, :w]

    blurred = np.zeros_like(a)
    for sigma, weight in ((0.8, 0.34), (2.6, 0.36), (7.5, 0.30)):
        blurred += weight * gaussian_filter(a, sigma=sigma, mode="nearest")
    m = float(blurred.max())
    if m > 0:
        blurred /= m
    # push the tail down so only the true hot spots stay bright
    return np.clip(blurred, 0.0, 1.0) ** 1.25


def _amber(v: np.ndarray) -> np.ndarray:
    """Dark navy -> amber ramp, identical for every scene."""
    v = np.clip(v, 0.0, 1.0)
    dark = np.array([10, 26, 58], dtype=np.float64)
    mid = np.array([138, 70, 20], dtype=np.float64)
    hot = np.array([255, 198, 104], dtype=np.float64)
    out = np.zeros(v.shape + (4,), dtype=np.float64)
    lo = v < 0.5
    t = (v[lo] / 0.5)[..., None]
    out[lo, :3] = dark * (1 - t) + mid * t
    hi = ~lo
    t2 = ((v[hi] - 0.5) / 0.5)[..., None]
    out[hi, :3] = mid * (1 - t2) + hot * t2
    out[..., 3] = np.clip(v * 1.35, 0.0, 1.0) * 255.0
    return (out / 255.0).astype(np.float32)


def _splat(field: np.ndarray, x: float, y: float, w: float) -> None:
    h, wd = field.shape
    px = int(round(x))
    py = int(round(y))
    if 0 <= px < wd and 0 <= py < h:
        field[py, px] += w


def _procedural_field(shape, extent, crs_srs) -> np.ndarray:
    """Density field from Natural Earth rivers + populated places.

    Points are projected into the SAME equal-area CRS as the base map, so a city
    light lands on the right pixel instead of on an equirectangular row.
    """
    import pyproj

    from . import natural_earth as ne

    h, w = shape
    field = np.zeros(shape, dtype=np.float64)
    minx, miny, maxx, maxy = extent
    spanx = max(1e-9, maxx - minx)
    spany = max(1e-9, maxy - miny)
    scale = min(w / spanx, h / spany)
    ox = (w - spanx * scale) / 2.0
    oy = (h - spany * scale) / 2.0

    t = pyproj.Transformer.from_crs("EPSG:4326", crs_srs, always_xy=True)

    def to_px(lon, lat):
        X, Y = t.transform(lon, lat)
        return ((X - minx) * scale + ox, (h - (Y - miny) * scale) - oy)

    # rivers: a thin skeleton, so the network shows
    from shapely.geometry import LineString, MultiLineString

    r = ne.rivers()
    sr = r["scalerank"].astype(float).clip(1, 8)
    for geom, rank in zip(r.geometry, sr):
        if geom is None or geom.is_empty:
            continue
        if isinstance(geom, MultiLineString):
            parts = list(geom.geoms)
        elif isinstance(geom, LineString):
            parts = [geom]
        else:
            continue
        wgt = 0.55 / (1.0 + (float(rank) - 1) * 0.6)
        for line in parts[:2]:
            xs, ys = line.xy
            step = max(1, len(xs) // 6)
            for x, y in zip(xs[::step], ys[::step]):
                px, py = to_px(x, y)
                _splat(field, px, py, wgt)

    # populated places weighted by log population
    for c in ne.major_places(1_000_000):
        px, py = to_px(c["lon"], c["lat"])
        _splat(field, px, py, 1.0 + 2.2 * float(np.log10(max(c["pop"], 1.0)) / 7.0))

    return field


def make_layer(source: dict, cache: Path, shape: tuple[int, int],
               extent=None, crs_srs: str = "EPSG:8857") -> np.ndarray:
    """Return an RGBA float32 glow tile for `shape` = (height, width)."""
    cache = Path(cache)
    src = source.get("source", "procedural")

    if src == "worldpop":
        tif = try_worldpop(cache)
        if tif:
            import rasterio

            with rasterio.open(tif) as ds:
                a = ds.read(1, out_shape=shape, resampling=rasterio.enums.Resampling.bilinear)
            return _amber(_finalise(a, shape))

    if src == "viirs":
        tif = try_viirs(cache)
        if tif:
            import rasterio

            with rasterio.open(tif) as ds:
                a = ds.read(1, out_shape=shape, resampling=tiff_resampling())
            return _amber(_finalise(a, shape))

    # procedural fallback
    try:
        if extent is None:
            raise ValueError("no extent")
        field = _procedural_field(shape, extent, crs_srs)
        return _amber(_finalise(field, shape))
    except Exception as exc:                       # never stop the build
        meta = META.parent / "glow_source.json"
        info = {}
        if meta.is_file():
            try:
                info = json.loads(meta.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                info = {}
        info.setdefault("source", "procedural")
        info["fallback_reason"] = f"{type(exc).__name__}: {exc}"
        META.write_text(json.dumps(info, indent=2), encoding="utf-8")
        h, w = shape
        v = np.clip(1.0 - np.abs(np.linspace(-1, 1, h))[:, None] ** 2, 0, 1)
        v = np.repeat(v, w, axis=1).astype(np.float32)
        return _amber(_finalise(v, shape))


def tiff_resampling():
    import rasterio

    return rasterio.enums.Resampling.bilinear


def resolve(cache: Path | None = None) -> dict:
    """Work the documented fallback chain and record what was actually used."""
    cache = Path(cache or (GEO / "cache"))
    if META.is_file():
        try:
            existing = json.loads(META.read_text(encoding="utf-8"))
            if existing.get("source") in ("worldpop", "viirs"):
                return existing
        except json.JSONDecodeError:
            pass
    tried = []
    if try_worldpop(cache):
        info = record("worldpop", tried=tried + ["worldpop"],
                      note="WorldPop 1 km-class global population mosaic, 2020")
        return info
    tried.append("worldpop")
    if try_viirs(cache):
        info = record("viirs", tried=tried + ["viirs"], note="VIIRS no-login annual composite")
        return info
    tried.append("viirs")
    return record("procedural", tried=tried,
                  reason="no no-login WorldPop or VIIRS raster was reachable; "
                         "density field rasterised from Natural Earth rivers and "
                         "populated places weighted by population")