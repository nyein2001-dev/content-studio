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
    rail_y: float
    rail_x1: float

    def rect(self, name: str) -> Rect:
        raw = self.zones[name]
        return Rect(raw["x"], raw["y"], raw["w"], raw["h"])

    def contains(self, name: str, box: Rect, eps: float = 0.51) -> bool:
        zone = self.rect(name)
        if name != "STAGE":
            return zone.contains(box, eps)
        if box.y < zone.y - eps or box.bottom > zone.bottom + eps:
            return False
        limit = self.zones["STAGE"]["full_x1"] if box.bottom <= self.rail_y + eps else self.rail_x1
        return box.x >= zone.x - eps and box.right <= limit + eps

    def stage_column(self) -> Rect:
        """Width that is legal for the full stage height (rail carved out)."""
        stage = self.rect("STAGE")
        return Rect(stage.x, stage.y, self.rail_x1 - stage.x, stage.h)


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
        item = {
            "role": zone["role"],
            "x": snap(zone["x"] * sx, grid),
            "y": snap(zone["y"] * sy, grid),
            "w": max(grid, snap(zone["w"] * sx, grid)),
            "h": max(grid, snap(zone["h"] * sy, grid)),
        }
        scaled[zone_name] = item
    stage = spec["zones"]["STAGE"]
    rail_y = snap(stage["rail_y"] * sy, grid)
    rail_x1 = snap(stage["rail_x1"] * sx, grid)
    full_x1 = scaled["STAGE"]["x"] + scaled["STAGE"]["w"]
    scaled["STAGE"]["full_x1"] = full_x1
    # Keep the footnote and caption from crossing the scaled rail.
    for band in ("FOOTNOTE", "CAPTION"):
        zone = scaled[band]
        zone["w"] = max(grid, min(zone["w"], rail_x1 - zone["x"]))
    return ZoneMap(name, int(canvas["width"]), int(canvas["height"]), scaled, float(rail_y), float(rail_x1))
