"""Placed scene graph. The renderer accepts these objects and nothing else."""
from __future__ import annotations

from dataclasses import dataclass

from layout.geom import Rect


@dataclass(frozen=True)
class Motion:
    start: int
    end: int
    opacity0: float = 0.0
    opacity1: float = 1.0
    scale0: float = 1.0
    scale1: float = 1.0
    slot: str = ""


@dataclass(frozen=True)
class Node:
    id: str
    kind: str
    zone: str
    rect: Rect
    content: Rect
    z: int
    text: str = ""
    font_role: str = ""
    font_size: float = 0.0
    font_key: str = ""
    color: str = "ink"
    ink: Rect | None = None
    parent: str | None = None
    glow: float = 0.0
    stroke: float = 0.0
    points: tuple[tuple[float, float], ...] = ()
    motion: Motion | None = None
    role: str = ""
    optional: bool = False
    fill: bool = False


@dataclass(frozen=True)
class Decision:
    action: str
    detail: str


@dataclass(frozen=True)
class PlacedScene:
    scene_id: str
    profile: str
    width: int
    height: int
    fps: int
    duration_frames: int
    nodes: tuple[Node, ...]
    legacy: bool = False
    decisions: tuple[Decision, ...] = ()
    caption_text: str = ""

    def by_id(self) -> dict[str, Node]:
        return {node.id: node for node in self.nodes}
