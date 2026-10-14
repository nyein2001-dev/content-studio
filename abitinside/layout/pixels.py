"""Pixel audit: real glyph masks, intersections, and contrast."""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image

from layout.brand import colour
from layout.model import PlacedScene
from layout.render import text_raster
from layout.rules import Violation
from layout.spec import load_spec
from layout.swept import sample_frames
from layout.zones import zones_for


def check_pixels(scene: PlacedScene, workers: int | None = None) -> list[Violation]:
    spec = load_spec()
    zones = zones_for(scene.profile)
    frames = sample_frames(scene.duration_frames, spec)
    texts = [node for node in scene.nodes if node.kind == "text" and node.text]
    masks = {node.id: _mask(node) for node in texts}
    found: list[Violation] = []
    with ThreadPoolExecutor(max_workers=workers or os.cpu_count() or 2) as pool:
        for batch in pool.map(lambda frame: _frame(scene, frame, texts, masks, zones, spec), frames):
            found.extend(batch)
    return found


def _mask(node) -> Image.Image:
    return text_raster(node).split()[-1]


def _frame(scene, frame, texts, masks, zones, spec) -> list[Violation]:
    found = []
    boxes = []
    for node in texts:
        mask = masks[node.id]
        alpha = np.array(mask)
        ys, xs = np.where(alpha > 16)
        if not len(xs):
            continue
        ink = (
            node.rect.x + float(xs.min()),
            node.rect.y + float(ys.min()),
            node.rect.x + float(xs.max()) + 1,
            node.rect.y + float(ys.max()) + 1,
        )
        boxes.append((node, ink, alpha))
        if ink[0] < -0.5 or ink[1] < -0.5 or ink[2] > scene.width + 0.5 or ink[3] > scene.height + 0.5:
            found.append(Violation(
                scene.scene_id, "LR-01", "fail",
                f"pixels of {node.text!r} leave the canvas on frame {frame}",
                "Shorten the line so the glyphs stay inside the zone.",
                (node.id,), frame,
            ))
        if not zones.contains(node.zone, node.rect):
            found.append(Violation(
                scene.scene_id, "LR-01", "fail",
                f"pixels of {node.text!r} leave {node.zone}",
                "Keep this text inside its zone.",
                (node.id,), frame,
            ))
        ratio = _contrast(node, alpha, scene.height)
        floor = spec["rules"]["contrast_large"] if node.font_size >= spec["rules"]["large_text_px"] else spec["rules"]["contrast_normal"]
        if ratio + 0.05 < floor:
            found.append(Violation(
                scene.scene_id, "LR-12", "fail",
                f"{node.text!r} contrast is {ratio:.2f}:1 and needs {floor}:1",
                "Use a theme token with enough contrast against the background.",
                (node.id,), frame, {"contrast": ratio},
            ))
    for i, (left, left_ink, left_alpha) in enumerate(boxes):
        for right, right_ink, right_alpha in boxes[i + 1:]:
            if left.parent and left.parent == right.parent:
                continue
            if not _overlap(left_ink, right_ink):
                continue
            if _masks_touch(left, left_alpha, right, right_alpha):
                found.append(Violation(
                    scene.scene_id, "LR-02", "fail",
                    f"glyphs {left.text!r} and {right.text!r} touch on frame {frame}",
                    "Separate these labels.",
                    (left.id, right.id), frame,
                ))
    return found


def _overlap(a, b) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _masks_touch(left, left_alpha, right, right_alpha) -> bool:
    x0 = int(max(left.rect.x, right.rect.x))
    y0 = int(max(left.rect.y, right.rect.y))
    x1 = int(min(left.rect.x + left_alpha.shape[1], right.rect.x + right_alpha.shape[1]))
    y1 = int(min(left.rect.y + left_alpha.shape[0], right.rect.y + right_alpha.shape[0]))
    if x1 <= x0 or y1 <= y0:
        return False
    la = left_alpha[y0 - int(left.rect.y): y1 - int(left.rect.y), x0 - int(left.rect.x): x1 - int(left.rect.x)]
    ra = right_alpha[y0 - int(right.rect.y): y1 - int(right.rect.y), x0 - int(right.rect.x): x1 - int(right.rect.x)]
    if la.shape != ra.shape or not la.size:
        return False
    return bool(np.any((la > 16) & (ra > 16)))


def _contrast(node, alpha, height: int) -> float:
    raster = np.array(text_raster(node).convert("RGB"))
    visible = alpha > 16
    if not np.any(visible):
        return 1.0
    text = raster[visible].astype(np.float32).mean(axis=0)
    mix = min(1.0, max(0.0, node.rect.cy / max(1, height - 1)))
    top = np.array(_rgb(colour("bg_top")), dtype=np.float32)
    bottom = np.array(_rgb(colour("bg_bottom")), dtype=np.float32)
    bg = top + (bottom - top) * mix
    return _ratio(text, bg)


def _ratio(fg, bg) -> float:
    def lum(rgb):
        value = rgb / 255.0
        linear = np.where(value <= 0.04045, value / 12.92, ((value + 0.055) / 1.055) ** 2.4)
        return float(0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2])

    a, b = lum(fg), lum(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def _rgb(hex_colour: str) -> tuple[int, int, int]:
    value = hex_colour.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-type]
