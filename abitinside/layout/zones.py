"""Zone rectangles scaled from the reference canvas in the spec."""
from __future__ import annotations

from dataclasses import dataclass

from layout.geom import Rect, snap
from layout.spec import load_spec


@dataclass(frozen=True)
class ZoneMap:
    profile: str
    width: int
    height: int
    zones: dict[str, dict]
    safe_x0: float
    safe_x1: float

    def rect(self, name: str) -> Rect:
        raw = self.zones[name]
        return Rect(raw["x"], raw["y"], raw["w"], raw["h"])

    def contains(self, name: str, box: Rect, eps: float = 0.51) -> bool:
        return self.rect(name).contains(box, eps)

    def in_safe_x(self, box: Rect, eps: float = 0.51) -> bool:
        return box.x >= self.safe_x0 - eps and box.right <= self.safe_x1 + eps

    def stage_column(self) -> Rect:
        return self.rect("STAGE")


def zones_for(profile: str | None = None) -> ZoneMap:
    spec = load_spec()
    name = profile or spec["default_profile"]
    if name not in spec["profiles"]:
        raise KeyError(f"unknown canvas profile {name!r}")
    ref = spec["reference"]
    canvas = spec["profiles"][name]
    sx = canvas["width"] / ref["width"]
    sy = canvas["height"] / ref["height"]
    grid = int(spec["grid"])
    scaled: dict[str, dict] = {}
    for zone_name, zone in spec["zones"].items():
        scaled[zone_name] = {
            "role": zone["role"],
            "x": snap(zone["x"] * sx, grid),
            "y": snap(zone["y"] * sy, grid),
            "w": max(grid, snap(zone["w"] * sx, grid)),
            "h": max(grid, snap(zone["h"] * sy, grid)),
            "align": zone.get("align", "center"),
        }
    safe = spec["safe"]
    return ZoneMap(
        name,
        int(canvas["width"]),
        int(canvas["height"]),
        scaled,
        float(snap(safe["x0"] * sx, grid)),
        float(snap(safe["x1"] * sx, grid)),
    )
