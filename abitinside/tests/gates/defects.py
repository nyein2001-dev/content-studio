"""Synthetic D1-D8 graphs. The validator must name the rule."""
from __future__ import annotations

from layout.geom import Rect
from layout.model import Node, PlacedScene
from layout.spec import load_spec


def _scene(nodes: list[Node], scene_id: str) -> PlacedScene:
    spec = load_spec()
    return PlacedScene(
        scene_id=scene_id,
        profile="portrait",
        width=1080,
        height=1920,
        fps=int(spec["fps"]),
        duration_frames=90,
        nodes=tuple(nodes),
    )


def _text(node_id: str, text: str, rect: Rect, parent: str | None, zone: str = "STAGE", role: str = "") -> Node:
    return Node(
        node_id, "text", zone, rect, rect, 4, text=text, ink=rect, parent=parent,
        font_role="body", font_size=32, font_key="bold", role=role,
    )


def d1_chip_overflow() -> PlacedScene:
    """COPELAND XWEB and DIXELL XWEB bleed out of fixed chips and into each other."""
    left = Rect(72, 700, 200, 56)
    right = Rect(280, 700, 200, 56)
    left_ink = Rect(160, 710, 220, 36)
    right_ink = Rect(300, 710, 210, 36)
    return _scene([
        Node("cope", "chip", "STAGE", left, left, 2, role="fixed"),
        _text("cope.t", "COPELAND XWEB", left_ink, "cope", role="fixed"),
        Node("dix", "chip", "STAGE", right, right, 2, role="fixed"),
        _text("dix.t", "DIXELL XWEB", right_ink, "dix", role="fixed"),
        Node("fill", "figure", "STAGE", Rect(72, 780, 800, 360), Rect(72, 780, 800, 360), 3, fill=True),
    ], "d1")


def d2_sibling_overlap() -> PlacedScene:
    return _scene([
        Node("chips", "chip", "STAGE", Rect(72, 700, 400, 80), Rect(72, 700, 400, 80), 2),
        Node("card", "card", "STAGE", Rect(72, 740, 500, 120), Rect(72, 740, 500, 120), 2),
        Node("fill", "figure", "STAGE", Rect(72, 900, 800, 300), Rect(72, 900, 800, 300), 3, fill=True),
    ], "d2")


def d3_caption_straddle() -> PlacedScene:
    card = Rect(120, 800, 640, 180)
    ink = Rect(140, 960, 420, 40)
    return _scene([
        Node("card", "card", "STAGE", card, Rect(144, 816, 592, 148), 2),
        Node("slot", "slot", "STAGE", ink, ink, 4, parent="card"),
        _text("slot.t", "built from the box's own date", ink, "slot"),
        Node("fill", "figure", "STAGE", Rect(72, 1040, 800, 200), Rect(72, 1040, 800, 200), 3, fill=True),
    ], "d3")


def d4_timeline() -> PlacedScene:
    axis = Rect(120, 900, 700, 4)
    aug = Rect(100, 912, 160, 36)
    oct_ = Rect(760, 912, 160, 36)
    return _scene([
        Node("axis", "axis", "STAGE", axis, axis, 3, role="axis", parent="line"),
        Node("line", "timeline", "STAGE", Rect(120, 860, 640, 120), Rect(120, 860, 640, 120), 2),
        Node("mark", "tick", "STAGE", Rect(140, 880, 4, 40), Rect(140, 880, 4, 40), 3, role="tick", parent="line"),
        Node("aug", "tick_label", "STAGE", aug, aug, 4, role="tick_label", parent="line", text="AUG 2025"),
        _text("aug.t", "AUG 2025", aug, "aug", role="tick_label"),
        Node("oct", "tick_label", "STAGE", oct_, oct_, 4, role="tick_label", parent="line", text="OCT 2026"),
        _text("oct.t", "OCT 2026", oct_, "oct", role="tick_label"),
    ], "d4")


def d5_badge() -> PlacedScene:
    badge = Rect(400, 980, 220, 36)
    return _scene([
        Node("card", "card", "STAGE", Rect(120, 800, 640, 160), Rect(120, 800, 640, 160), 2),
        Node("badge", "chip", "STAGE", badge, badge, 4, role="badge", text="ILLUSTRATIVE"),
        _text("badge.t", "ILLUSTRATIVE", badge, "badge", role="badge"),
        Node("label", "chip", "STAGE", Rect(390, 960, 240, 40), Rect(390, 960, 240, 40), 2),
    ], "d5")


def d6_connectors() -> PlacedScene:
    text = Rect(400, 900, 280, 40)
    icon = Rect(360, 860, 80, 80)
    pill = Rect(350, 850, 120, 48)
    return _scene([
        Node("icon", "icon", "STAGE", icon, icon, 3, role="icon"),
        Node("pill", "chip", "STAGE", pill, pill, 2, role="label"),
        Node("slot", "slot", "STAGE", text, text, 4),
        _text("slot.t", "one box runs every case", text, "slot"),
        Node(
            "spoke", "connector", "STAGE", Rect(200, 700, 400, 400), Rect(200, 700, 400, 400), 1,
            points=((200, 700), (500, 920), (700, 1100)),
        ),
        Node("fill", "figure", "STAGE", Rect(72, 1100, 800, 160), Rect(72, 1100, 800, 160), 3, fill=True),
    ], "d6")


def d7_gap() -> PlacedScene:
    return _scene([
        Node("top", "card", "STAGE", Rect(120, 620, 400, 80), Rect(120, 620, 400, 80), 2),
        Node("bot", "card", "STAGE", Rect(120, 1100, 400, 80), Rect(120, 1100, 400, 80), 2),
    ], "d7")


def d8_caption() -> PlacedScene:
    ink = Rect(200, 1500, 680, 80)
    return _scene([
        Node("art", "card", "STAGE", Rect(120, 1400, 700, 120), Rect(120, 1400, 700, 120), 2),
        Node("cap", "caption", "CAPTION", ink, ink, 6),
        _text("cap.t", "opened an inquiry", ink, "cap", zone="CAPTION"),
    ], "d8")


DEFECTS = {
    "D1": (d1_chip_overflow, {"LR-03", "LR-04", "LR-05"}),
    "D2": (d2_sibling_overlap, {"LR-02"}),
    "D3": (d3_caption_straddle, {"LR-03"}),
    "D4": (d4_timeline, {"LR-08"}),
    "D5": (d5_badge, {"LR-09"}),
    "D6": (d6_connectors, {"LR-06", "LR-07"}),
    "D7": (d7_gap, {"LR-10"}),
    "D8": (d8_caption, {"LR-01", "LR-14"}),
}
