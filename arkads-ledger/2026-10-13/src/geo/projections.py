"""Equal-area projections.

Every map in this channel is reprojected to an equal-area CRS so an area on the
picture means the same thing everywhere on it. World views use Equal Earth
(EPSG:8857, geographic centre on Greenwich); regional views use a Lambert
Azimuthal Equal Area centred on the region.
"""
from __future__ import annotations

import functools

import pyproj

WORLD_EPSG = 8857          # WGS 84 / Equal Earth Greenwich
WORLD = "EPSG:8857"


def world_equal_area() -> pyproj.CRS:
    """Equal Earth. Equal-area, visually far better than Mollweide."""
    return pyproj.CRS.from_epsg(WORLD_EPSG)


def region_equal_area(lat0: float, lon0: float) -> pyproj.CRS:
    """LAEA centred on (lat0, lon0): equal area and readable for a region."""
    return pyproj.CRS.from_proj4(
        f"+proj=laea +lat_0={lat0} +lon_0={lon0} +datum=WGS84 +units=m +no_defs")


EQUAL_AREA_METHODS = ("equal earth", "lambert azimuthal equal area",
                       "albers", "cylindrical equal area", "mollweide",
                       "sinusoidal", "eckert", "equal earth cylindrical")


def is_equal_area(crs: pyproj.CRS) -> bool:
    """pyproj has no is_equal_area flag, so read the projection method name."""
    try:
        method = (crs.coordinate_operation.method_name or "").lower()
    except Exception:
        return False
    return any(m in method for m in EQUAL_AREA_METHODS)


def equal_area(crs: str | int) -> pyproj.CRS:
    c = pyproj.CRS.from_user_input(crs)
    if not c.is_projected or not is_equal_area(c):
        raise ValueError(f"{crs} is not an equal-area projected CRS")
    return c


def geodesic_to(points_lonlat: list[tuple[float, float]],
                transformer: pyproj.Transformer, n: int = 48) -> list[list[tuple[float, float]]]:
    """Densify a lon/lat polyline geodesically, then project it.

    Projecting only the original vertices would turn a great-circle route into a
    flat chord, so every segment is interpolated on the WGS84 geodesic first.
    Returns one projected polyline per input segment.
    """
    from pyproj import Geod

    geod = Geod(ellps="WGS84")
    pts = list(points_lonlat)
    if len(pts) < 2:
        xs, ys = transformer.transform([p[0] for p in pts], [p[1] for p in pts])
        return [list(zip(xs, ys))]

    dense: list[list[float]] = []
    for i in range(len(pts) - 1):
        (lon1, lat1), (lon2, lat2) = pts[i], pts[i + 1]
        if i == 0:
            dense.append([float(lon1), float(lat1)])
        mid = geod.npts(lon1, lat1, lon2, lat2, max(1, n - 2))
        dense.extend([float(a), float(b)] for a, b in mid)
        dense.append([float(lon2), float(lat2)])
    xs, ys = transformer.transform([p[0] for p in dense], [p[1] for p in dense])
    return [list(zip(xs, ys))]


@functools.lru_cache(maxsize=8)
def transformer(src: str = "EPSG:4326", dst: str = WORLD) -> pyproj.Transformer:
    return pyproj.Transformer.from_crs(src, dst, always_xy=True)


def project_lonlat(points: list[tuple[float, float]], crs: str | int = WORLD,
                   densify: int = 0) -> list[tuple[float, float]]:
    t = transformer("EPSG:4326", pyproj.CRS.from_user_input(crs).to_string())
    if densify:
        return geodesic_to(points, t, densify)[0]
    xs, ys = t.transform([p[0] for p in points], [p[1] for p in points])
    return list(zip(xs, ys))