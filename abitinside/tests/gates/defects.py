"""Synthetic D1-D8 graphs. The validator must name the rule."""
from __future__ import annotations

from layout.geom import Rect
from layout.model import Motion, Node, PlacedScene
from layout.spec import load_spec


def _scene(nodes: list[Node], scene_id: str, frames: int = 90) -> PlacedScene:
    spec = load_spec()
    return PlacedScene(
        scene_id=scene_id,
        profile="portrait",
        width=1080,
        height=1920,
        fps=int(spec["fps"]),
        duration_frames=frames,
        nodes=tuple(nodes),
        caption_text="by morning",
    )


def _text(node_id: str, text: str, rect: Rect, parent: str | None, zone: str = "STAGE", role: str = "") -> Node:
    return Node(
        node_id, "text", zone, rect, rect, 4, text=text, ink=rect, parent=parent,
        font_role="stage", font_size=36, font_key="regular", role=role,
    )


def d1_chip_overflow() -> PlacedScene:
    left = Rect(200, 800, 180, 72)
    right = Rect(300, 800, 180, 72)
    left_ink = Rect(280, 808, 160, 30)
    return _scene([
        Node("cope", "chip", "STAGE", left, left, 3, role="label"),
        _text("cope.t", "COPELAND XWEB", left_ink, "cope"),
        Node("dix", "chip", "STAGE", right, right, 3, role="label"),
        Node("fill", "figure", "STAGE", Rect(200, 900, 600, 200), Rect(200, 900, 600, 200), 3, fill=True),
    ], "d1")


def d2_timeline() -> PlacedScene:
    label = Rect(40, 900, 160, 36)
    return _scene([
        Node("axis", "axis", "STAGE", Rect(200, 960, 600, 4), Rect(200, 960, 600, 4), 3, role="axis"),
        Node("aug", "tick_label", "STAGE", label, label, 4, role="tick_label", text="AUG 2025"),
        _text("aug.t", "AUG 2025", label, "aug"),
        Node(
            "spoke", "connector", "STAGE", Rect(40, 880, 400, 80), Rect(40, 880, 400, 80), 2,
            points=((20, 910), (180, 910)),
        ),
    ], "d2")


def d3_card_overflow() -> PlacedScene:
    card = Rect(200, 800, 400, 120)
    ink = Rect(160, 860, 500, 40)
    return _scene([
        Node("card", "card", "STAGE", card, Rect(224, 824, 352, 72), 3),
        Node("slot", "slot", "STAGE", ink, ink, 4, parent="card"),
        _text("slot.t", "built from the box's own date", ink, "slot"),
    ], "d3")


def d4_same_slot() -> PlacedScene:
    return _scene([
        Node(
            "login", "card", "STAGE", Rect(200, 760, 400, 100), Rect(224, 784, 352, 52), 3,
            motion=Motion(0, 40, slot="auth"),
        ),
        Node(
            "code", "card", "STAGE", Rect(200, 900, 400, 100), Rect(224, 924, 352, 52), 3,
            motion=Motion(20, 60, slot="auth"),
        ),
    ], "d4")


def d5_badge() -> PlacedScene:
    badge = Rect(400, 900, 220, 36)
    return _scene([
        Node("badge", "chip", "STAGE", badge, badge, 4, role="badge", text="ILLUSTRATIVE"),
        _text("badge.t", "ILLUSTRATIVE", badge, "badge", role="badge"),
    ], "d5")


def d6_connector() -> PlacedScene:
    text = Rect(400, 900, 280, 40)
    return _scene([
        Node("slot", "slot", "STAGE", text, text, 4),
        _text("slot.t", "the engineer has to clear it", text, "slot"),
        Node(
            "line", "connector", "STAGE", Rect(200, 800, 500, 200), Rect(200, 800, 500, 200), 2,
            points=((220, 820), (500, 920)),
        ),
    ], "d6")


def d7_pills() -> PlacedScene:
    icon = Rect(300, 900, 120, 140)
    pill = Rect(310, 940, 100, 48)
    label = Rect(320, 950, 80, 28)
    return _scene([
        Node("case", "icon", "STAGE", icon, icon, 3, role="icon"),
        Node("probes", "chip", "STAGE", pill, pill, 3, role="label"),
        _text("probes.t", "PROBES", label, "probes"),
        Node(
            "spoke", "connector", "STAGE", Rect(200, 800, 300, 200), Rect(200, 800, 300, 200), 2,
            points=((220, 860), (360, 960)),
        ),
    ], "d7")


def d8_dead_space() -> PlacedScene:
    return _scene([
        Node("only", "card", "STAGE", Rect(200, 668, 400, 80), Rect(224, 684, 352, 48), 3),
    ], "d8")


DEFECTS = {
    "D1": (d1_chip_overflow, {"R03", "R05", "R06", "R07", "R10"}),
    "D2": (d2_timeline, {"R01", "R08"}),
    "D3": (d3_card_overflow, {"R03"}),
    "D4": (d4_same_slot, {"R11"}),
    "D5": (d5_badge, {"R01"}),
    "D6": (d6_connector, {"R08"}),
    "D7": (d7_pills, {"R05", "R08"}),
    "D8": (d8_dead_space, {"R16"}),
}
