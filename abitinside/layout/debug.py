"""Debug overlays and a contact sheet."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from layout.brand import colour
from layout.model import PlacedScene
from layout.render import render_frame
from layout.rules import Violation
from layout.spec import load_spec
from layout.zones import zones_for


def debug_frame(
    scene: PlacedScene,
    violations: list[Violation] | None = None,
    frame: int | None = None,
) -> Image.Image:
    if frame is None:
        frame = scene.duration_frames // 2
    frame = min(max(0, int(frame)), max(0, scene.duration_frames - 1))
    image = render_frame(scene, frame).convert("RGBA")
    draw = ImageDraw.Draw(image)
    zones = zones_for(scene.profile)
    for name, zone in zones.zones.items():
        rect = (zone["x"], zone["y"], zone["x"] + zone["w"], zone["y"] + zone["h"])
        hue = colour("coral") if zone["role"] == "keepout" else colour("cyan")
        draw.rectangle(rect, outline=hue)
    for node in scene.nodes:
        if node.kind in ("text", "slot"):
            continue
        draw.rectangle(
            (node.rect.x, node.rect.y, node.rect.right, node.rect.bottom),
            outline=colour("green"),
        )
    for node in scene.nodes:
        if node.ink is None:
            continue
        draw.rectangle(
            (node.ink.x, node.ink.y, node.ink.right, node.ink.bottom),
            outline=colour("yellow"),
        )
    for item in violations or []:
        if item.severity != "fail":
            continue
        draw.text((24, 24), f"{item.rule} {item.message[:80]}", fill=colour("coral"))
        break
    return image.convert("RGB")


def annotate(scene: PlacedScene, item: Violation) -> Image.Image:
    """One red-box PNG for a violation, drawn on the frame where it was measured."""
    image = debug_frame(scene, frame=item.frame).convert("RGBA")
    draw = ImageDraw.Draw(image)
    ids = set(item.element_ids)
    drawn = False
    for node in scene.nodes:
        if node.id in ids or (node.parent and node.parent in ids):
            draw.rectangle(
                (node.rect.x, node.rect.y, node.rect.right, node.rect.bottom),
                outline=(255, 40, 40),
                width=4,
            )
            drawn = True
    if not drawn:
        draw.rectangle((24, 24, scene.width - 24, 96), outline=(255, 40, 40), width=4)
    return image.convert("RGB")


def contact_sheet(scenes: list[PlacedScene], path: Path, violations: dict[str, list[Violation]] | None = None) -> Path:
    spec = load_spec()
    scale = float(spec["debug"]["contact_scale"])
    columns = int(spec["debug"]["contact_columns"])
    frames = []
    for scene in scenes:
        for frame in (0, scene.duration_frames // 2, max(0, scene.duration_frames - 1)):
            shot = debug_frame(scene, (violations or {}).get(scene.scene_id), frame=frame)
            frames.append(shot.resize((int(shot.width * scale), int(shot.height * scale)), Image.Resampling.BILINEAR))
    if not frames:
        raise RuntimeError("no scenes for the contact sheet")
    cell_w, cell_h = frames[0].size
    rows = (len(frames) + columns - 1) // columns
    sheet = Image.new("RGB", (cell_w * columns, cell_h * rows), colour("bg_top"))
    for index, frame in enumerate(frames):
        sheet.paste(frame, ((index % columns) * cell_w, (index // columns) * cell_h))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
    return path
