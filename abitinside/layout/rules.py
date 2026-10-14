"""Geometry rules R01 through R16."""
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
    found.extend(_text_pairs(scene, frame))
    found.extend(_slots(scene, spec, frame))
    found.extend(_type_floor(scene, spec, frame))
    found.extend(_reading(scene, spec, frame))
    found.extend(_density(scene, spec, frame))
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
        if not zones.contains(node.zone, visual) or (
            node.zone != "PLATFORM_TOP" and node.zone != "PLATFORM_BOTTOM" and not zones.in_safe_x(visual)
        ):
            found.append(Violation(
                scene.scene_id, "R01", "fail",
                f"{node.id} is not fully inside {node.zone}",
                "Move this element into its zone or shorten it in the DSL.",
                (node.id,), frame, {"zone": node.zone, "box": [visual.x, visual.y, visual.w, visual.h]},
            ))
        for name in keepouts:
            if node.kind in ("background",) or node.z <= 0:
                continue
            if zones.rect(name).intersects(visual):
                found.append(Violation(
                    scene.scene_id, "R02", "fail",
                    f"{node.id} enters the {name} keepout",
                    "Keep text and charts out of the platform keepouts.",
                    (node.id,), frame, {"keepout": name},
                ))
    return found


def _known_parents(scene: PlacedScene) -> set[str]:
    return {node.id for node in scene.nodes}


def _top(node: Node, ids: set[str]) -> bool:
    return node.parent is None or node.parent not in ids


def _concurrent(left: Node, right: Node) -> bool:
    left_motion = left.motion
    right_motion = right.motion
    if left_motion is None or right_motion is None:
        return True
    if not left_motion.slot or left_motion.slot != right_motion.slot:
        return True
    return not (left_motion.end <= right_motion.start or right_motion.end <= left_motion.start)


def _siblings(scene, spec, frame) -> list[Violation]:
    ids = _known_parents(scene)
    tops = [node for node in scene.nodes if _top(node, ids) and node.kind not in ("connector", "connector_request")]
    found = []
    gap_default = float(spec["spacing"]["sibling_gap"])
    chip_gap = float(spec["spacing"]["chip_gap"])
    for i, left in enumerate(tops):
        for right in tops[i + 1:]:
            if not _concurrent(left, right):
                continue
            required = chip_gap if left.kind == "chip" and right.kind == "chip" else gap_default
            if left.rect.intersects(right.rect):
                found.append(Violation(
                    scene.scene_id, "R06", "fail",
                    f"{left.id} overlaps {right.id}",
                    "Separate these containers. Sibling boxes may not overlap.",
                    (left.id, right.id), frame,
                ))
            if left.rect.gap(right.rect) + 0.2 < required:
                found.append(Violation(
                    scene.scene_id, "R07", "fail",
                    f"{left.id} is only {left.rect.gap(right.rect):.0f}px from {right.id}",
                    f"Leave at least {required:.0f}px between these containers.",
                    (left.id, right.id), frame,
                ))
            if left.glow and right.ink and left.rect.inflate(left.glow).intersects(right.ink):
                found.append(Violation(
                    scene.scene_id, "R05", "fail",
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
            owner = parent
            while owner is not None and owner.kind in ("slot", "tick_label"):
                owner = by_id.get(owner.parent or "")
            container = owner.rect if owner is not None and owner.kind in ("chip", "card", "code_panel", "stat", "notice") else None
            pad = float(spec["spacing"]["text_edge_gap"])
            if container is not None and not container.inflate(-pad).contains(ink):
                found.append(Violation(
                    scene.scene_id, "R03", "fail",
                    f"text {node.text!r} leaves its container {owner.id}",
                    "Let the container grow from the measured text, or shorten the words.",
                    (node.id, owner.id), frame,
                ))
            elif not parent.content.contains(ink):
                found.append(Violation(
                    scene.scene_id, "R03", "fail",
                    f"text {node.text!r} leaves its container {parent.id}",
                    "Let the container grow from the measured text, or shorten the words.",
                    (node.id, parent.id), frame,
                ))
            if parent.role == "fixed" or node.role == "fixed":
                found.append(Violation(
                    scene.scene_id, "R09", "fail",
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
                    scene.scene_id, "R03", "fail",
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
                scene.scene_id, "R10", "fail",
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
                if segment_hits_rect(
                    start[0], start[1], end[0], end[1], target,
                    pad=float(spec["spacing"]["connector_inflate"]),
                ):
                    found.append(Violation(
                        scene.scene_id, "R08", "fail",
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
                    scene.scene_id, "R05", "fail",
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
            if label.rect.gap(tick.rect) < minimum:
                found.append(Violation(
                    scene.scene_id, "R01", "fail",
                    f"tick label {label.id} collides with its tick",
                    "Move the label at least 24px off the tick mark.",
                    (label.id, tick.id), frame,
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
        if not zones.contains("BADGE", node.rect):
            found.append(Violation(
                scene.scene_id, "R01", "fail",
                f"badge {node.id} is outside the BADGE zone",
                "Set the scene badge flag. The template draws ILLUSTRATIVE only in the BADGE zone.",
                (node.id,), frame,
            ))
    for node in scene.nodes:
        if node.kind != "text" or "ILLUSTRATIVE" not in node.text:
            continue
        slot = scene.by_id().get(node.parent or "")
        host = slot.rect if slot else node.rect
        if zones.contains("BADGE", host):
            continue
        found.append(Violation(
            scene.scene_id, "R01", "fail",
            "ILLUSTRATIVE is outside the BADGE zone",
            "Remove the badge from the stage. The template owns the BADGE zone.",
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
            scene.scene_id, "R16", "fail",
            "the stage has no content",
            "Add a chart, card, or diagram.",
            frame=frame,
        )]
    top = min(node.rect.y for node in stage_nodes)
    bottom = max(node.rect.bottom for node in stage_nodes)
    stage = zones.rect("STAGE")
    above = top - stage.y
    below = stage.bottom - bottom
    found = []
    if abs(above - below) > float(spec["spacing"]["dead_space_imbalance"]) + 0.5:
        found.append(Violation(
            scene.scene_id, "R16", "fail",
            f"stage dead space is unbalanced ({above:.0f}px above, {below:.0f}px below)",
            "Center the stage stack. Do not leave a crowded band opposite an empty one.",
            frame=frame, measured={"above": above, "below": below},
        ))
    ordered = sorted(stage_nodes, key=lambda node: node.rect.y)
    limit = float(spec["spacing"]["max_stack_gap"])
    for left, right in zip(ordered, ordered[1:]):
        if left.parent or right.parent:
            continue
        gap = right.rect.y - left.rect.bottom
        if gap > limit:
            found.append(Violation(
                scene.scene_id, "R16", "fail",
                f"empty gap of {gap:.0f}px between {left.id} and {right.id}",
                "Close the hole in the stack. Do not leave a dead band between stage components.",
                (left.id, right.id), frame, {"gap": gap},
            ))
    return found


def _caption(scene, zones: ZoneMap, frame) -> list[Violation]:
    caption = zones.rect("SUBTITLE")
    found = []
    for node in scene.nodes:
        if node.zone == "SUBTITLE":
            continue
        if node.kind in ("connector",):
            continue
        if node.rect.intersects(caption):
            found.append(Violation(
                scene.scene_id, "R01", "fail",
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
                scene.scene_id, "R09", "fail",
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
                scene.scene_id, "R11", "fail",
                f"text {node.id} is under the connectors",
                "Keep type above lines.",
                (node.id,), frame,
            ))
        if node.kind == "cursor":
            for other in scene.nodes:
                if other.kind == "text" and node.rect.intersects(other.rect):
                    target = node.role == "overlay" and other.parent and node.id.endswith(other.parent)
                    if target:
                        continue
                    found.append(Violation(
                        scene.scene_id, "R11", "fail",
                        f"cursor {node.id} covers {other.id}",
                        "Move the cursor into an empty corner.",
                        (node.id, other.id), frame,
                    ))
    return found


_SHAPE = {"chip", "card", "figure", "icon", "axis", "tick", "stat", "timeline", "code_panel"}


def _ancestors(scene, node: Node) -> set[str]:
    found = set()
    current = node
    seen = set()
    while current.parent and current.parent not in seen:
        seen.add(current.parent)
        found.add(current.parent)
        current = scene.by_id().get(current.parent)
        if current is None:
            break
    return found


def _text_pairs(scene, frame) -> list[Violation]:
    texts = [node for node in scene.nodes if node.kind == "text" and node.ink]
    shapes = [node for node in scene.nodes if node.kind in _SHAPE or node.role in ("icon", "axis", "tick")]
    found = []
    for index, left in enumerate(texts):
        for right in texts[index + 1:]:
            if left.parent and left.parent == right.parent:
                continue
            if not _concurrent(left, right):
                continue
            ink_l = left.ink or left.rect
            ink_r = right.ink or right.rect
            if ink_l.intersects(ink_r):
                found.append(Violation(
                    scene.scene_id, "R04", "fail",
                    f"text {left.id} overlaps text {right.id}",
                    "Shorten one of these strings or move them into separate slots.",
                    (left.id, right.id), frame,
                ))
    for text in texts:
        owners = _ancestors(scene, text)
        ink = text.ink or text.rect
        for shape in shapes:
            if shape.id in owners or shape.id == text.id:
                continue
            if not _concurrent(text, shape):
                continue
            if ink.intersects(shape.rect):
                found.append(Violation(
                    scene.scene_id, "R05", "fail",
                    f"text {text.id} crosses {shape.id}",
                    "Keep type off shapes it does not belong to.",
                    (text.id, shape.id), frame,
                ))
    return found


def _slots(scene, spec, frame) -> list[Violation]:
    found = []
    groups: dict[str, list[Node]] = {}
    for node in scene.nodes:
        if node.motion is None or not node.motion.slot:
            continue
        groups.setdefault(node.motion.slot, []).append(node)
    gap = float(spec["spacing"]["slot_gap_s"]) * scene.fps
    for slot, nodes in groups.items():
        windows = sorted({(node.motion.start, node.motion.end) for node in nodes})
        for left, right in zip(windows, windows[1:]):
            if right[0] < left[1] + gap:
                found.append(Violation(
                    scene.scene_id, "R11", "fail",
                    f"slot {slot} overlaps at frames {left[0]}-{left[1]} and {right[0]}-{right[1]}",
                    "Finish the exit, wait 0.1s, then enter the replacement.",
                    (slot,), frame, {"slot": slot},
                ))
    return found


def _type_floor(scene, spec, frame) -> list[Violation]:
    found = []
    for node in scene.nodes:
        if node.kind != "text" or not node.font_role:
            continue
        from layout.text import canonical_role
        role = canonical_role(node.font_role)
        floor = spec["type"].get(role, {}).get("floor")
        if floor is not None and node.font_size + 0.1 < floor:
            found.append(Violation(
                scene.scene_id, "R09", "fail",
                f"{node.id} is {node.font_size:.0f}px, under the {role} floor {floor}",
                "Do not draw text below the type minimum.",
                (node.id,), frame,
            ))
    return found


def _reading(scene, spec, frame) -> list[Violation]:
    if scene.legacy:
        return []
    words = len((scene.caption_text or "").split())
    needed = max(float(spec["rules"]["reading_min_s"]), words / float(spec["rules"]["reading_words_per_s"]))
    duration = scene.duration_frames / float(scene.fps or spec["fps"])
    if duration + 1e-6 < needed:
        return [Violation(
            scene.scene_id, "R14", "fail",
            f"text is on screen for {duration:.2f}s and needs {needed:.2f}s",
            "Lengthen the beat so the subtitle can be read.",
            frame=frame,
        )]
    return []


def _density(scene, spec, frame) -> list[Violation]:
    found = []
    stage = [
        node for node in scene.nodes
        if node.zone == "STAGE" and node.parent is None and node.kind not in ("text", "slot", "connector", "connector_request")
    ]
    limit = int(spec["rules"]["max_stage_elements"])
    if len(stage) > limit:
        found.append(Violation(
            scene.scene_id, "R12", "fail",
            f"{len(stage)} stage elements exceeds {limit}",
            "Remove a component or split the scene.",
            tuple(node.id for node in stage), frame,
        ))
    return found
