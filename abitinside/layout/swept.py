"""Per-frame geometry. Opacity never lets two text nodes share pixels."""
from __future__ import annotations

from dataclasses import replace

from layout.geom import Rect
from layout.model import Node, PlacedScene
from layout.render import opacity_at
from layout.rules import Violation, check_scene
from layout.spec import load_spec


def sample_frames(duration: int, spec: dict | None = None, nodes=()) -> list[int]:
    """Every Nth frame, the last frame, and enter/exit padded by the spec."""
    spec = spec or load_spec()
    step = max(1, int(spec["rules"]["pixel_sample_every"]))
    pad = int(spec["rules"]["sample_pad_frames"])
    frames = set(range(0, max(duration, 1), step))
    frames.add(0)
    frames.add(max(0, duration - 1))
    for node in nodes:
        motion = getattr(node, "motion", None)
        if motion is None:
            continue
        for edge in (int(motion.start), int(motion.end)):
            for delta in range(-pad, pad + 1):
                frame = edge + delta
                if 0 <= frame < duration:
                    frames.add(frame)
    return sorted(frames)


def check_swept(scene: PlacedScene) -> list[Violation]:
    spec = load_spec()
    found: list[Violation] = []
    max_scale = float(spec["rules"]["max_scale"])
    for frame in range(scene.duration_frames):
        live = []
        visible = []
        for node in scene.nodes:
            alpha = opacity_at(node, frame)
            scale = _scale(node, frame)
            if scale > max_scale + 1e-6:
                found.append(Violation(
                    scene.scene_id, "R11", "fail",
                    f"{node.id} scales to {scale:.2f} on frame {frame}",
                    "Keep scale at or below the maximum in the spec.",
                    (node.id,), frame,
                ))
            rect = _scaled(node.rect, scale)
            if not node.rect.contains(rect, eps=1.0):
                found.append(Violation(
                    scene.scene_id, "R01", "fail",
                    f"{node.id} leaves its slot on frame {frame}",
                    "Animate inside the reserved slot only.",
                    (node.id,), frame,
                ))
            ink = None if node.ink is None else _scaled_about(node.ink, node.rect, scale)
            scaled = replace(node, rect=rect, content=_scaled_about(node.content, node.rect, scale), ink=ink)
            live.append(scaled)
            if alpha > 0.01:
                visible.append(scaled)
        found.extend(_text_collisions(scene.scene_id, visible, frame))
        probed = replace(scene, nodes=tuple(live))
        found.extend(item for item in check_scene(probed, frame=frame) if item.rule != "LEGACY-UNMIGRATED" or scene.legacy)
    return _unique(found)


def _scale(node: Node, frame: int) -> float:
    motion = node.motion
    if motion is None:
        return 1.0
    if frame <= motion.start:
        return motion.scale0
    if frame >= motion.end:
        return motion.scale1
    t = (frame - motion.start) / max(1, motion.end - motion.start)
    return motion.scale0 + (motion.scale1 - motion.scale0) * t


def _scaled(rect: Rect, scale: float) -> Rect:
    if abs(scale - 1.0) < 1e-6:
        return rect
    w = rect.w * scale
    h = rect.h * scale
    return Rect(rect.cx - w / 2.0, rect.cy - h / 2.0, w, h)


def _scaled_about(rect: Rect, origin: Rect, scale: float) -> Rect:
    if abs(scale - 1.0) < 1e-6:
        return rect
    return Rect(
        origin.cx + (rect.x - origin.cx) * scale,
        origin.cy + (rect.y - origin.cy) * scale,
        rect.w * scale,
        rect.h * scale,
    )


def _text_collisions(scene: str, nodes: list[Node], frame: int) -> list[Violation]:
    texts = [node for node in nodes if node.kind == "text"]
    found = []
    for i, left in enumerate(texts):
        for right in texts[i + 1:]:
            if not left.rect.intersects(right.rect):
                continue
            same = left.motion and right.motion and left.motion.slot and left.motion.slot == right.motion.slot
            if same:
                continue
            found.append(Violation(
                scene, "R11", "fail",
                f"{left.text!r} and {right.text!r} occupy the same pixels on frame {frame}",
                "Give them separate slots, or sequence them so the first has left before the second appears.",
                (left.id, right.id), frame,
            ))
    cursors = [node for node in nodes if node.kind == "cursor"]
    for cursor in cursors:
        for text in texts:
            if cursor.rect.intersects(text.rect):
                found.append(Violation(
                    scene, "R11", "fail",
                    f"cursor covers {text.text!r} on frame {frame}",
                    "Move the cursor off the type.",
                    (cursor.id, text.id), frame,
                ))
    return found


def _unique(found: list[Violation]) -> list[Violation]:
    seen = set()
    out = []
    for item in found:
        key = (item.rule, item.element_ids, item.frame, item.message)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
