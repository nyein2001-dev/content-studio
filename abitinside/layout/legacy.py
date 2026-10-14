"""Read the frozen episode renderer and turn its ink into a legacy scene graph.

The episode sources are not modified. This module only calls them.
"""
from __future__ import annotations

import sys
from pathlib import Path

from layout.geom import Rect
from layout.model import Node, PlacedScene
from layout.spec import ABIT, load_spec


def probe_episode(day: Path | None = None) -> list[PlacedScene]:
    day = day or (ABIT / "2026-10-13")
    src = day / "src"
    render = src / "render"
    for path in (src, render, ABIT):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)
    from engine import Text, install_fonts, new_surface
    import scenes

    install_fonts()
    spec = load_spec()
    fps = int(spec["fps"])
    graphs = []
    for name, fn in scenes.SCENES.items():
        if name == "endcard":
            continue
        fake = {
            "id": name,
            "start_frame": 0,
            "end_frame": 180,
            "beats": ["one", "two", "three", "four"],
            "headline": ["LEGACY", "SCENE"],
            "captions": [],
        }
        nodes: list[Node] = []
        for frame in (21, 150):
            nodes.extend(_capture(fn, fake, frame, Text, new_surface))
        graphs.append(PlacedScene(
            scene_id=name,
            profile="portrait",
            width=1080,
            height=1920,
            fps=fps,
            duration_frames=90,
            nodes=tuple(_dedupe(nodes)),
            legacy=True,
            caption_text="legacy caption",
        ))
    return graphs


def _capture(fn, fake, frame: int, text_cls, new_surface) -> list[Node]:
    import components
    import engine
    import scenes

    surface, context = new_surface()
    recorded: list[tuple] = []
    saved = {
        "draw": engine.Text.draw,
        "stroke": engine.stroke_colour,
        "fill": engine.fill_colour,
        "line": engine.line,
    }

    def draw(self, x, y, s, colour, alpha=1.0):
        extents = self.cr.text_extents(s or " ")
        size = float(self._cur[1]) if self._cur else 0.0
        ink = Rect(
            x + extents.x_bearing, y + extents.y_bearing,
            max(extents.width, 1.0), max(extents.height, 1.0),
        )
        recorded.append(("text", s or "", ink, size))
        return saved["draw"](self, x, y, s, colour, alpha)

    def stroke_colour(cr, colour, width=3, alpha=1.0):
        try:
            x0, y0, x1, y1 = cr.path_extents()
            if x1 > x0 and y1 > y0:
                recorded.append(("shape", Rect(x0, y0, x1 - x0, y1 - y0)))
        except Exception:
            pass
        return saved["stroke"](cr, colour, width, alpha)

    def fill_colour(cr, colour, alpha=1.0):
        try:
            x0, y0, x1, y1 = cr.path_extents()
            if x1 > x0 and y1 > y0:
                recorded.append(("shape", Rect(x0, y0, x1 - x0, y1 - y0)))
        except Exception:
            pass
        return saved["fill"](cr, colour, alpha)

    def line(cr, x0, y0, x1, y1, colour, width=3, alpha=1.0, dash=None):
        recorded.append(("line", [(float(x0), float(y0)), (float(x1), float(y1))]))
        return saved["line"](cr, x0, y0, x1, y1, colour, width, alpha, dash)

    engine.Text.draw = draw
    for module in (engine, components, scenes):
        module.stroke_colour = stroke_colour
        module.fill_colour = fill_colour
        module.line = line
    try:
        txt = text_cls(context)
        fn(context, txt, frame, fake)
    finally:
        engine.Text.draw = saved["draw"]
        for module in (engine, components, scenes):
            module.stroke_colour = saved["stroke"]
            module.fill_colour = saved["fill"]
            module.line = saved["line"]
        surface.finish()
    return _nodes(recorded, frame)


def _nodes(recorded: list[tuple], frame: int) -> list[Node]:
    shapes = [item[1] for item in recorded if item[0] == "shape"]
    nodes: list[Node] = []
    index = 0
    for kind, *rest in recorded:
        if kind != "text":
            continue
        text, ink, size = rest
        host = _host(ink, shapes)
        zone = _zone(ink)
        parent = None
        if host is not None:
            parent = f"box-{frame}-{index}"
            role = "fixed" if not host.contains(ink, eps=1) else ""
            if text in {"AUG 2025", "OCT 2026"}:
                role = "tick_label"
            nodes.append(Node(
                parent, "chip" if host.w < 500 else "card", zone, host, host, 2,
                role="fixed" if role == "fixed" else ("tick_label" if text in {"AUG 2025", "OCT 2026"} else ""),
            ))
        node_role = "tick_label" if text in {"AUG 2025", "OCT 2026"} else ("badge" if text == "ILLUSTRATIVE" else "")
        nodes.append(Node(
            f"text-{frame}-{index}", "text", zone, ink, ink, 4,
            text=text, ink=ink, parent=parent, font_size=size, font_key="bold",
            role=node_role or ("fixed" if parent and host is not None and not host.contains(ink, eps=1) else ""),
        ))
        index += 1
    for line_index, item in enumerate(recorded):
        if item[0] != "line":
            continue
        points = item[1]
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        box = Rect(min(xs), min(ys), max(1, max(xs) - min(xs)), max(1, max(ys) - min(ys)))
        if box.w < 8 and box.h < 8:
            continue
        kind = "tick" if box.h > box.w * 2 and box.h < 80 else "connector"
        nodes.append(Node(
            f"line-{frame}-{line_index}", kind, _zone(box), box, box, 1,
            points=tuple(points), role="tick" if kind == "tick" else "",
        ))
    return nodes


def _host(ink: Rect, shapes: list[Rect]) -> Rect | None:
    point_hosts = []
    for shape in shapes:
        if shape.x <= ink.cx <= shape.right and shape.y <= ink.y <= shape.bottom + 20:
            point_hosts.append(shape)
    if not point_hosts:
        return None
    return min(point_hosts, key=lambda shape: shape.w * shape.h)


def _zone(rect: Rect) -> str:
    spec = load_spec()
    cy = rect.cy
    for name, zone in spec["zones"].items():
        if zone["role"] != "content":
            continue
        if zone["y"] <= cy <= zone["y"] + zone["h"]:
            return name
    return "STAGE"


def _dedupe(nodes: list[Node]) -> list[Node]:
    seen = set()
    out = []
    for node in nodes:
        key = (node.kind, node.text, round(node.rect.x, 1), round(node.rect.y, 1), round(node.rect.w, 1))
        if key in seen:
            continue
        seen.add(key)
        out.append(node)
    return out
