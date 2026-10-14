"""Geometry rules LR-01 through LR-15."""
from __future__ import annotations

from dataclasses import dataclass, field

from layout.geom import Rect, segment_hits_rect
from layout.model import Node, PlacedScene
from layout.spec import load_spec
from layout.zones import ZoneMap, zones_for


@dataclass
class Violation:
    scene: str
    rule: str
    severity: str
    message: str
    remedy: str
    element_ids: tuple[str, ...] = ()
    frame: int | None = None
    measured: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "scene": self.scene,
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "remedy": self.remedy,
            "element_ids": list(self.element_ids),
            "frame": self.frame,
            "measured": self.measured,
        }


_DECOR = {"slot", "text", "underline", "series", "tick", "tick_label", "meter", "figure", "axis", "connector"}


def check_scene(scene: PlacedScene, zones: ZoneMap | None = None, frame: int | None = None) -> list[Violation]:
    spec = load_spec()
    zones = zones or zones_for(scene.profile)
    found: list[Violation] = []
    if scene.legacy:
        found.append(Violation(
            scene.scene_id, "LEGACY-UNMIGRATED", "fail",
            "this scene is still drawn by the old coordinate renderer",
            "Rebuild the scene in the DSL and run the gate again. The old file cannot be published.",
            frame=frame,
        ))
    found.extend(_safe(scene, zones, spec, frame))
    found.extend(_siblings(scene, spec, frame))
    found.extend(_containment(scene, spec, frame))
    found.extend(_center(scene, spec, frame))
    found.extend(_connectors(scene, spec, frame))
    found.extend(_labels(scene, spec, frame))
    found.extend(_ticks(scene, spec, frame))
    found.extend(_badges(scene, zones, frame))
    found.extend(_balance(scene, zones, spec, frame))
    found.extend(_caption(scene, zones, frame))
    found.extend(_counters(scene, frame))
    found.extend(_zorder(scene, spec, frame))
    return found


def hard_failures(found: list[Violation]) -> list[Violation]:
    return [item for item in found if item.severity == "fail"]


def _safe(scene, zones: ZoneMap, spec, frame) -> list[Violation]:
    found = []
    keepouts = [name for name, zone in zones.zones.items() if spec["zones"][name]["role"] == "keepout"]
    for node in scene.nodes:
        if node.kind == "connector":
            continue
        visual = node.rect.inflate(node.glow + node.stroke / 2.0)
        if not zones.contains(node.zone, visual):
            found.append(Violation(
                scene.scene_id, "LR-01", "fail",
                f"{node.id} is not fully inside {node.zone}",
                "Move this element into its zone or shorten it in the DSL.",
                (node.id,), frame, {"zone": node.zone},
            ))
        for name in keepouts:
            if zones.rect(name).intersects(visual):
                found.append(Violation(
                    scene.scene_id, "LR-01", "fail",
                    f"{node.id} enters the {name} keepout",
                    "Keep text and charts out of the platform and right-rail keepouts.",
                    (node.id,), frame, {"keepout": name},
                ))
    return found


def _known_parents(scene: PlacedScene) -> set[str]:
    return {node.id for node in scene.nodes}


def _top(node: Node, ids: set[str]) -> bool:
    return node.parent is None or node.parent not in ids


def _siblings(scene, spec, frame) -> list[Violation]:
    ids = _known_parents(scene)
    tops = [node for node in scene.nodes if _top(node, ids) and node.kind not in ("connector", "connector_request")]
    found = []
    gap_default = float(spec["spacing"]["sibling_gap"])
    chip_gap = float(spec["spacing"]["chip_gap"])
    for i, left in enumerate(tops):
        for right in tops[i + 1:]:
            required = chip_gap if left.kind == "chip" and right.kind == "chip" else gap_default
            if left.rect.intersects(right.rect):
                found.append(Violation(
                    scene.scene_id, "LR-02", "fail",
                    f"{left.id} overlaps {right.id}",
                    "Separate these containers. Sibling boxes may not overlap.",
                    (left.id, right.id), frame,
                ))
            elif left.rect.gap(right.rect) + 0.2 < required:
                found.append(Violation(
                    scene.scene_id, "LR-02", "fail",
                    f"{left.id} is only {left.rect.gap(right.rect):.0f}px from {right.id}",
                    f"Leave at least {required:.0f}px between these containers.",
                    (left.id, right.id), frame,
                ))
            if left.glow and right.ink and left.rect.inflate(left.glow).intersects(right.ink):
                found.append(Violation(
                    scene.scene_id, "LR-02", "fail",
                    f"glow on {left.id} covers text {right.id}",
                    "Reduce the glow or move the text. Glow may not cover type.",
                    (left.id, right.id), frame,
                ))
    return found


def _containment(scene, spec, frame) -> list[Violation]:
    by_id = scene.by_id()
    found = []
    for node in scene.nodes:
        if node.kind == "text" and node.parent in by_id:
            parent = by_id[node.parent]
            ink = node.ink or node.rect
            if not parent.content.contains(ink):
                found.append(Violation(
                    scene.scene_id, "LR-03", "fail",
                    f"text {node.text!r} leaves its container {parent.id}",
                    "Let the container grow from the measured text, or shorten the words.",
                    (node.id, parent.id), frame,
                ))
            if parent.role == "fixed" or node.role == "fixed":
                found.append(Violation(
                    scene.scene_id, "LR-04", "fail",
                    f"{node.text!r} is forced into a fixed box",
                    "Remove the fixed size and let the chip hug the label.",
                    (node.id,), frame,
                ))
        if node.parent in by_id and node.kind not in ("connector",):
            parent = by_id[node.parent]
            if node.kind == "text":
                continue
            if not parent.rect.contains(node.rect):
                found.append(Violation(
                    scene.scene_id, "LR-03", "fail",
                    f"{node.id} is not inside {parent.id}",
                    "Keep the child inside the parent's inner rectangle.",
                    (node.id, parent.id), frame,
                ))
    return found


def _center(scene, spec, frame) -> list[Violation]:
    tol = float(spec["spacing"]["center_tolerance"])
    by_parent: dict[str, list[Node]] = {}
    for node in scene.nodes:
        if node.kind == "text" and node.parent:
            by_parent.setdefault(node.parent, []).append(node)
    by_id = scene.by_id()
    found = []
    for parent_id, texts in by_parent.items():
        parent = by_id.get(parent_id)
        if parent is None:
            continue
        union = texts[0].rect
        for text in texts[1:]:
            union = union.union(text.rect)
        dx = abs(union.cx - parent.content.cx)
        dy = abs(union.cy - parent.content.cy)
        if dx > tol or dy > tol:
            found.append(Violation(
                scene.scene_id, "LR-05", "fail",
                f"text in {parent_id} is off center by {dx:.1f}px, {dy:.1f}px",
                "Center the ink in the container. Do not pin the text to a corner of a fixed chip.",
                tuple(text.id for text in texts), frame, {"dx": dx, "dy": dy},
            ))
    return found


def _connectors(scene, spec, frame) -> list[Violation]:
    texts = [node for node in scene.nodes if node.kind == "text" and node.ink]
    icons = [node for node in scene.nodes if node.role == "icon" or node.kind == "icon"]
    found = []
    for node in scene.nodes:
        if node.kind != "connector" or len(node.points) < 2:
            continue
        blocked = texts + icons
        for start, end in zip(node.points, node.points[1:]):
            for other in blocked:
                target = other.ink or other.rect
                if segment_hits_rect(start[0], start[1], end[0], end[1], target):
                    found.append(Violation(
                        scene.scene_id, "LR-06", "fail",
                        f"connector {node.id} crosses {other.id}",
                        "Reroute the connector around the label, or remove it.",
                        (node.id, other.id), frame,
                    ))
    return found


def _labels(scene, spec, frame) -> list[Violation]:
    found = []
    icons = [node for node in scene.nodes if node.role == "icon" or node.kind in ("icon", "card", "stat")]
    labels = [node for node in scene.nodes if node.kind == "chip" or node.role == "label"]
    gap = float(spec["spacing"]["chip_gap"])
    for label in labels:
        for icon in icons:
            if label.id == icon.id or label.parent == icon.id:
                continue
            if label.rect.intersects(icon.rect):
                found.append(Violation(
                    scene.scene_id, "LR-07", "fail",
                    f"label {label.id} sits on {icon.id}",
                    "Put the label in a slot above, below, or beside the icon, with a gap.",
                    (label.id, icon.id), frame,
                ))
            elif label.rect.gap(icon.rect) < gap and label.rect.gap(icon.rect) > 0:
                # Only flag chips that were meant to name a touching icon. A far chip is fine.
                pass
    return found


def _ticks(scene, spec, frame) -> list[Violation]:
    labels = [node for node in scene.nodes if node.role == "tick_label" or node.kind == "tick_label"]
    ticks = [node for node in scene.nodes if node.role == "tick" or node.kind == "tick"]
    axes = [node for node in scene.nodes if node.role == "axis" or node.kind in ("axis", "line_chart", "bar_chart", "timeline")]
    found = []
    minimum = float(spec["spacing"]["tick_gap"])
    for label in labels:
        for tick in ticks:
            if label.rect.intersects(tick.rect) or (
                label.rect.gap(tick.rect) < minimum and _near(label.rect, tick.rect, minimum * 4)
            ):
                if label.rect.gap(tick.rect) < minimum:
                    found.append(Violation(
                        scene.scene_id, "LR-08", "fail",
                        f"tick label {label.id} collides with its tick",
                        "Move the label at least 12px off the tick mark.",
                        (label.id, tick.id), frame,
                    ))
        for axis in axes:
            if label.parent and axis.id != label.parent and not axis.id.startswith(str(label.parent)):
                continue
            if label.rect.right > axis.rect.right + 0.6 or label.rect.x < axis.rect.x - 0.6:
                found.append(Violation(
                    scene.scene_id, "LR-08", "fail",
                    f"tick label {label.id} runs past the axis",
                    "Right-align the last label and keep it inside the axis extent.",
                    (label.id, axis.id), frame,
                ))
    # Labels against each other.
    ordered = sorted(labels, key=lambda node: node.rect.x)
    chip_gap = float(spec["spacing"]["chip_gap"])
    for left, right in zip(ordered, ordered[1:]):
        if left.parent != right.parent:
            continue
        if left.rect.gap(right.rect) < chip_gap and not left.optional:
            found.append(Violation(
                scene.scene_id, "LR-08", "fail",
                f"tick labels {left.id} and {right.id} collide",
                "Shorten the labels, or mark alternate ticks optional in the DSL.",
                (left.id, right.id), frame,
            ))
    return found


def _near(a: Rect, b: Rect, limit: float) -> bool:
    return a.gap(b) <= limit or a.inflate(limit).intersects(b)


def _badges(scene, zones: ZoneMap, frame) -> list[Violation]:
    found = []
    for node in scene.nodes:
        if "ILLUSTRATIVE" not in (node.text or "") and node.role != "badge":
            continue
        if node.kind == "text":
            continue
        in_note = zones.contains("FOOTNOTE", node.rect)
        parent_ok = False
        if node.parent:
            parent = scene.by_id().get(node.parent)
            if parent and parent.rect.contains(node.rect):
                parent_ok = True
        if not in_note and not parent_ok:
            found.append(Violation(
                scene.scene_id, "LR-09", "fail",
                f"badge {node.id} is floating between components",
                "Put ILLUSTRATIVE in the footnote slot or in a corner inside its card.",
                (node.id,), frame,
            ))
    # Text that says ILLUSTRATIVE and whose slot is not in the footnote or inside a card.
    for node in scene.nodes:
        if node.kind != "text" or "ILLUSTRATIVE" not in node.text:
            continue
        slot = scene.by_id().get(node.parent or "")
        host = slot.rect if slot else node.rect
        if zones.contains("FOOTNOTE", host):
            continue
        container = None
        if slot and slot.parent:
            container = scene.by_id().get(slot.parent)
        if container and container.rect.contains(host):
            continue
        found.append(Violation(
            scene.scene_id, "LR-09", "fail",
            "ILLUSTRATIVE is not in the footnote or inside its card",
            "Move this disclaimer into the footnote line or a corner that stays inside the card.",
            (node.id,), frame,
        ))
    return found


def _balance(scene, zones: ZoneMap, spec, frame) -> list[Violation]:
    stage_nodes = [
        node for node in scene.nodes
        if node.zone == "STAGE" and node.kind not in (
            "connector", "connector_request", "text", "slot", "cursor",
        ) and node.role != "overlay"
    ]
    if not stage_nodes:
        return [Violation(
            scene.scene_id, "LR-10", "fail",
            "the stage has no content",
            "Add a chart, card, or diagram.",
            frame=frame,
        )]
    top = min(node.rect.y for node in stage_nodes)
    bottom = max(node.rect.bottom for node in stage_nodes)
    height = bottom - top
    stage = zones.rect("STAGE")
    ratio = height / stage.h if stage.h else 0
    found = []
    if ratio + 1e-6 < float(spec["rules"]["stage_fill_fail"]):
        found.append(Violation(
            scene.scene_id, "LR-10", "fail",
            f"stage content fills {ratio:.0%} of the stage",
            "Scale the illustration up or add the missing component. A large empty stage fails the gate.",
            frame=frame, measured={"fill": ratio},
        ))
    elif ratio < float(spec["rules"]["flex_target"]):
        found.append(Violation(
            scene.scene_id, "LR-10", "warn",
            f"stage content fills {ratio:.0%} of the stage",
            "Grow the illustration toward 60% of the stage height.",
            frame=frame, measured={"fill": ratio},
        ))
    ordered = sorted(stage_nodes, key=lambda node: node.rect.y)
    limit = float(spec["spacing"]["max_stack_gap"])
    for left, right in zip(ordered, ordered[1:]):
        if left.parent or right.parent:
            continue
        gap = right.rect.y - left.rect.bottom
        if gap > limit:
            found.append(Violation(
                scene.scene_id, "LR-10", "fail",
                f"empty gap of {gap:.0f}px between {left.id} and {right.id}",
                "Close the hole in the stack. Do not leave a dead band between stage components.",
                (left.id, right.id), frame, {"gap": gap},
            ))
    return found


def _caption(scene, zones: ZoneMap, frame) -> list[Violation]:
    caption = zones.rect("CAPTION")
    found = []
    for node in scene.nodes:
        if node.zone == "CAPTION":
            continue
        if node.kind in ("connector",):
            continue
        if node.rect.intersects(caption):
            found.append(Violation(
                scene.scene_id, "LR-14", "fail",
                f"{node.id} enters the caption band",
                "Keep stage art and footnotes out of the caption zone.",
                (node.id,), frame,
            ))
    return found


def _counters(scene, frame) -> list[Violation]:
    found = []
    for node in scene.nodes:
        if node.role != "counter" or node.kind != "text":
            continue
        if node.font_key != "mono":
            found.append(Violation(
                scene.scene_id, "LR-15", "fail",
                f"counter {node.id} is not monospace",
                "Draw live numbers in the mono face so the width stays stable.",
                (node.id,), frame,
            ))
    return found


def _zorder(scene, spec, frame) -> list[Violation]:
    order = spec["z_order"]
    found = []
    for node in scene.nodes:
        if node.kind == "text" and node.z < order["connectors"]:
            found.append(Violation(
                scene.scene_id, "LR-11", "fail",
                f"text {node.id} is under the connectors",
                "Keep type above lines.",
                (node.id,), frame,
            ))
        if node.kind == "cursor":
            for other in scene.nodes:
                if other.kind == "text" and node.rect.intersects(other.rect):
                    found.append(Violation(
                        scene.scene_id, "LR-11", "fail",
                        f"cursor {node.id} covers {other.id}",
                        "Move the cursor into an empty corner.",
                        (node.id, other.id), frame,
                    ))
    return found
