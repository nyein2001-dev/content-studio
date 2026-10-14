"""Constraint layout. Scenes bring semantic components; this file produces slots."""
from __future__ import annotations

from dataclasses import replace

from layout.budget import check_budget
from layout.errors import LayoutError
from layout.fit import FittedText, fit_text, try_fit
from layout.geom import Rect
from layout.metrics import measure
from layout.model import Decision, Motion, Node, PlacedScene
from layout.router import anchors, route
from layout.spec import load_spec
from layout.zones import ZoneMap, zones_for


def solve(doc: dict) -> list[PlacedScene]:
    problems = check_budget(doc)
    if problems:
        first = problems[0]
        raise LayoutError(doc["id"], "LR-13", first, "Edit the scene DSL until the density budget passes.")
    spec = load_spec()
    scale = float(doc.get("scale_to") or 1.0)
    if scale > float(spec["rules"]["max_scale"]):
        raise LayoutError(
            doc["id"], "LR-11",
            f"scale {scale} exceeds {spec['rules']['max_scale']}",
            "Keep scale_to at or below the maximum in layout_spec.yaml.",
        )
    try:
        return [_place(doc, doc.get("stage") or [], spec)]
    except LayoutError:
        if not doc.get("splittable"):
            raise
        return _split(doc, spec)


def _split(doc: dict, spec: dict) -> list[PlacedScene]:
    stage = list(doc.get("stage") or [])
    if len(stage) < 2:
        raise LayoutError(
            doc["id"], "LR-04",
            "this scene does not fit and has nothing to split",
            "Shorten the wording or remove a component. Splitting needs at least two stage components.",
        )
    minimum = float(spec["rules"]["min_scene_duration_s"])
    half = float(doc["duration_s"]) / 2.0
    if half < minimum:
        raise LayoutError(
            doc["id"], "LR-13",
            "splitting this scene would make a beat shorter than the minimum duration",
            "Lengthen the narration before marking the scene splittable, or cut a component.",
        )
    mid = max(1, len(stage) // 2)
    placed = []
    for index, group in enumerate((stage[:mid], stage[mid:])):
        child = dict(doc)
        child["id"] = f"{doc['id']}_beat{index + 1}"
        child["stage"] = group
        child["duration_s"] = half
        child["splittable"] = False
        child["connectors"] = []
        scene = _place(child, group, spec)
        scene = replace(
            scene,
            decisions=scene.decisions + (Decision("split", f"beat {index + 1} keeps the original caption"),),
        )
        placed.append(scene)
    return placed


def _place(doc: dict, stage: list, spec: dict) -> PlacedScene:
    zones = zones_for(doc.get("profile"))
    decisions: list[Decision] = []
    frames = max(1, int(round(float(doc["duration_s"]) * spec["fps"])))
    motion = _motion(frames, spec)
    nodes: list[Node] = []
    nodes.extend(_brand(doc, zones, spec, motion))
    nodes.extend(_headline(doc, zones, spec, motion, decisions))
    nodes.extend(_caption(doc, zones, spec, motion, decisions))
    if doc.get("footnote"):
        nodes.extend(_footnote(doc, zones, spec, motion))
    column = zones.stage_column()
    # Stroke is drawn on the rectangle edge, so the box itself sits half a stroke inside.
    half = float(spec["spacing"]["stroke"]) / 2.0
    column = column.inflate(-half)
    blocks = [_component(doc["id"], comp, column, spec, motion, decisions, zones) for comp in stage]
    blocks = _grow(doc["id"], blocks, column, spec, motion, decisions)
    _stack(doc["id"], blocks, column, spec)
    for block in blocks:
        nodes.extend(block.nodes)
    if doc.get("overlay"):
        nodes.extend(_overlay(doc, nodes, column, spec, motion, zones))
    _connectors(doc, nodes, zones, spec)
    _assert_inside(doc["id"], nodes, zones)
    return PlacedScene(
        scene_id=doc["id"],
        profile=zones.profile,
        width=zones.width,
        height=zones.height,
        fps=int(spec["fps"]),
        duration_frames=frames,
        nodes=tuple(nodes),
        decisions=tuple(decisions),
        caption_text=doc["caption"],
    )


def _motion(frames: int, spec: dict) -> Motion:
    end = min(int(spec["rules"]["enter_frames"]), frames)
    return Motion(0, max(1, end))


def _z(spec: dict, name: str) -> int:
    return int(spec["z_order"][name])


def _center_in(fitted: FittedText, inner: Rect) -> list[tuple[str, Rect]]:
    y = inner.cy - fitted.height / 2.0
    placed = []
    for line, ink in zip(fitted.lines, fitted.inks):
        width = max(ink.width, 1.0)
        height = max(ink.height, 1.0)
        x = inner.cx - width / 2.0
        placed.append((line, Rect(x, y, width, height)))
        y += ink.height + fitted.line_gap
    return placed


def _text_nodes(parent: str, zone: str, fitted: FittedText, inner: Rect, z: int, color: str, motion: Motion, role: str = "") -> list[Node]:
    placed = _center_in(fitted, inner)
    union = placed[0][1]
    for _, ink_rect in placed[1:]:
        union = union.union(ink_rect)
    slot_id = f"{parent}.slot{int(round(inner.y))}x{int(round(inner.x))}"
    nodes = [Node(
        slot_id, "slot", zone, union, union, z, parent=parent, motion=motion, role=role,
    )]
    for index, (line, ink_rect) in enumerate(placed):
        nodes.append(Node(
            id=f"{slot_id}.t{index}",
            kind="text",
            zone=zone,
            rect=ink_rect,
            content=ink_rect,
            ink=ink_rect,
            z=z,
            text=line,
            font_role=fitted.role,
            font_size=fitted.size,
            font_key=fitted.font_key,
            color=color,
            parent=slot_id,
            motion=motion,
            role=role,
        ))
    return nodes


def _slot(parent: str, zone: str, rect: Rect, z: int, motion: Motion, kind: str = "slot") -> Node:
    return Node(parent, kind, zone, rect, rect, z, parent=None, motion=motion, fill=False)


def _brand(doc, zones: ZoneMap, spec, motion) -> list[Node]:
    zone = zones.rect("BRAND")
    pad_x = spec["spacing"]["text_pad_x"]
    fitted = fit_text(doc["id"], doc["brand"], "brand", zone.w - 2 * pad_x, max_lines=1)
    bar_w = float(spec["spacing"]["xs"])
    gap = float(spec["spacing"]["s"])
    group_w = bar_w + gap + fitted.width
    group_h = max(fitted.height, bar_w * 2)
    group = Rect(zone.cx - group_w / 2.0, zone.cy - group_h / 2.0, group_w, group_h)
    bar = Rect(group.x, group.cy - group_h / 2.0, bar_w, group_h)
    text_inner = Rect(group.x + bar_w + gap, group.cy - fitted.height / 2.0, fitted.width, fitted.height)
    nodes = [
        Node("brand", "brand", "BRAND", group, group, _z(spec, "content"), motion=motion, color="cyan"),
        Node("brand.bar", "figure", "BRAND", bar, bar, _z(spec, "content"), parent="brand", color="cyan", fill=True, motion=motion),
    ]
    nodes.extend(_text_nodes("brand", "BRAND", fitted, text_inner, _z(spec, "text"), "ink", motion))
    return nodes


def _headline(doc, zones, spec, motion, decisions) -> list[Node]:
    zone = zones.rect("HEADLINE")
    pad_x = spec["spacing"]["text_pad_x"]
    fitted = fit_text(doc["id"], doc["headline"], "headline", zone.w - 2 * pad_x)
    _note_shrink(decisions, "headline", fitted, spec)
    gap = float(spec["spacing"]["line_gap"])
    underline_h = float(spec["spacing"]["underline_h"])
    block_h = fitted.height + gap + underline_h
    block_w = fitted.width
    group = Rect(zone.cx - block_w / 2.0, zone.cy - block_h / 2.0, block_w, block_h)
    text_inner = Rect(group.x, group.y, block_w, fitted.height)
    underline = Rect(group.x, text_inner.bottom + gap, block_w, underline_h)
    nodes = [Node("headline", "headline", "HEADLINE", group, group, _z(spec, "containers"), motion=motion)]
    nodes.extend(_text_nodes("headline", "HEADLINE", fitted, text_inner, _z(spec, "text"), "ink", motion))
    nodes.append(Node(
        "headline.underline", "underline", "HEADLINE", underline, underline,
        _z(spec, "content"), parent="headline", color="cyan", fill=True, motion=motion,
    ))
    return nodes


def _caption(doc, zones, spec, motion, decisions) -> list[Node]:
    zone = zones.rect("CAPTION")
    pad_x = spec["spacing"]["text_pad_x"]
    fitted = fit_text(doc["id"], doc["caption"], "caption", zone.w - 2 * pad_x)
    _note_shrink(decisions, "caption", fitted, spec)
    if fitted.height > zone.h:
        raise LayoutError(
            doc["id"], "LR-04",
            f"caption is {fitted.height:.0f}px tall and the caption band is {zone.h:.0f}px",
            "Shorten the caption so two lines stay inside the caption band.",
        )
    group = Rect(
        zone.x + pad_x,
        zone.cy - fitted.height / 2.0,
        zone.w - 2 * pad_x,
        fitted.height,
    )
    nodes = [Node(
        "caption", "caption", "CAPTION", group, group, _z(spec, "caption"), motion=motion,
    )]
    nodes.extend(_text_nodes("caption", "CAPTION", fitted, group, _z(spec, "caption"), "ink", motion))
    return nodes


def _footnote(doc, zones, spec, motion) -> list[Node]:
    zone = zones.rect("FOOTNOTE")
    pad_x = spec["spacing"]["text_pad_x"]
    fitted = fit_text(doc["id"], doc["footnote"], "footnote", zone.w - 2 * pad_x, max_lines=1)
    group = Rect(zone.cx - fitted.width / 2.0, zone.cy - fitted.height / 2.0, fitted.width, fitted.height)
    nodes = [Node("footnote", "footnote", "FOOTNOTE", group, group, _z(spec, "text"), role="badge", motion=motion)]
    nodes.extend(_text_nodes("footnote", "FOOTNOTE", fitted, group, _z(spec, "text"), "ink_dim", motion))
    return nodes


def _note_shrink(decisions: list[Decision], name: str, fitted: FittedText, spec: dict) -> None:
    preferred = spec["type"][fitted.role]["preferred"]
    if fitted.size < preferred:
        decisions.append(Decision("shrink", f"{name} {preferred}px -> {fitted.size:.0f}px"))


class _Block:
    def __init__(self, nodes: list[Node], height: float, flex: bool):
        self.nodes = nodes
        self.height = height
        self.flex = flex

    @property
    def top(self) -> float:
        return min(node.rect.y for node in self.nodes)

    def shift(self, dy: float) -> None:
        if abs(dy) < 1e-6:
            return
        moved = []
        for node in self.nodes:
            ink = None if node.ink is None else Rect(node.ink.x, node.ink.y + dy, node.ink.w, node.ink.h)
            points = tuple((x, y + dy) for x, y in node.points)
            moved.append(replace(
                node,
                rect=Rect(node.rect.x, node.rect.y + dy, node.rect.w, node.rect.h),
                content=Rect(node.content.x, node.content.y + dy, node.content.w, node.content.h),
                ink=ink,
                points=points,
            ))
        self.nodes = moved


def _component(scene, comp, column: Rect, spec, motion, decisions, zones) -> _Block:
    kind = comp["type"]
    builder = {
        "chip_row": _chips,
        "card": _card,
        "stat": _stat,
        "line_chart": _chart,
        "bar_chart": _chart,
        "timeline": _timeline,
        "flow": _flow,
        "hub_and_spoke": _hub,
        "code_panel": _code,
        "severity_meter": _meter,
        "callout": _card,
        "checklist": _checklist,
        "comparison": _comparison,
    }[kind]
    return builder(scene, comp, column, spec, motion, decisions, zones)


def _chips(scene, comp, column, spec, motion, decisions, zones) -> _Block:
    labels = list(comp.get("labels") or [])
    if not labels:
        raise LayoutError(scene, "LR-04", f"{comp['id']} has no chip labels", "Add label text in the DSL.")
    pad_x = float(spec["spacing"]["chip_pad_x"])
    pad_y = float(spec["spacing"]["chip_pad_y"])
    gap = float(spec["spacing"]["chip_gap"])
    step = int(spec["spacing"]["shrink_step"])
    size = int(spec["type"]["chip"]["preferred"])
    floor = int(spec["type"]["chip"]["floor"])
    placed = None
    used = size
    while size >= floor:
        trial = []
        ok = True
        for label in labels:
            fitted = try_fit(label, "chip", column.w - 2 * pad_x, size, max_lines=1)
            if fitted is None:
                ok = False
                break
            trial.append(fitted)
        if not ok:
            if size == floor:
                break
            size = max(floor, size - step)
            continue
        widths = [item.width + 2 * pad_x for item in trial]
        height = max(item.height for item in trial) + 2 * pad_y
        if sum(widths) + gap * (len(widths) - 1) <= column.w + 0.1:
            placed = ("row", trial, widths, height)
            used = size
            break
        # Reflow into wrapped rows before giving up this size.
        rows: list[list[int]] = [[]]
        row_w = 0.0
        for index, width in enumerate(widths):
            extra = width if not rows[-1] else width + gap
            if rows[-1] and row_w + extra > column.w:
                rows.append([])
                row_w = 0.0
                extra = width
            rows[-1].append(index)
            row_w += extra
        if len(rows) > 1:
            placed = ("grid", trial, widths, height, rows)
            used = size
            decisions.append(Decision("reflow", f"{comp['id']} chips wrapped to {len(rows)} rows"))
            break
        if size == floor:
            break
        size = max(floor, size - step)
    if placed is None:
        if comp.get("alternate") != "vertical":
            raise LayoutError(
                scene, "LR-04",
                f"chips in {comp['id']} do not fit {column.w:.0f}px",
                "Declare alternate: vertical, or shorten the chip labels.",
            )
        decisions.append(Decision("alternate", f"{comp['id']} chip row became a vertical list"))
        return _chips_vertical(scene, comp, column, spec, motion, labels)
    if used < int(spec["type"]["chip"]["preferred"]):
        decisions.append(Decision("shrink", f"{comp['id']} chips {spec['type']['chip']['preferred']}px -> {used}px"))
    return _chips_place(scene, comp, column, spec, motion, placed, pad_x, pad_y, gap)


def _chips_place(scene, comp, column, spec, motion, placed, pad_x, pad_y, gap) -> _Block:
    mode = placed[0]
    trial = placed[1]
    widths = placed[2]
    height = placed[3]
    y = 0.0
    nodes: list[Node] = []
    if mode == "row":
        total_w = sum(widths) + gap * (len(widths) - 1)
        x = column.x + (column.w - total_w) / 2.0
        for index, fitted in enumerate(trial):
            _append_chip(nodes, comp["id"], index, fitted, x, y, widths[index], height, spec, motion, pad_x, pad_y)
            x += widths[index] + gap
        block_h = height
    else:
        rows = placed[4]
        block_h = 0.0
        for row in rows:
            row_w = sum(widths[i] for i in row) + gap * (len(row) - 1)
            x = column.x + (column.w - row_w) / 2.0
            for index in row:
                _append_chip(nodes, comp["id"], index, trial[index], x, y, widths[index], height, spec, motion, pad_x, pad_y)
                x += widths[index] + gap
            y += height + gap
            block_h = y - gap
    return _Block(nodes, block_h, True)


def _append_chip(nodes, cid, index, fitted, x, y, width, height, spec, motion, pad_x, pad_y) -> None:
    rect = Rect(x, y, width, height)
    inner = Rect(x + pad_x, y + pad_y, width - 2 * pad_x, height - 2 * pad_y)
    node_id = f"{cid}.{index}"
    nodes.append(Node(
        node_id, "chip", "STAGE", rect, inner, _z(spec, "containers"),
        parent=cid, motion=motion, color="cyan", stroke=float(spec["spacing"]["stroke"]), role="label",
    ))
    nodes.extend(_text_nodes(node_id, "STAGE", fitted, inner, _z(spec, "text"), "cyan", motion))


def _chips_vertical(scene, comp, column, spec, motion, labels) -> _Block:
    pad_x = float(spec["spacing"]["chip_pad_x"])
    pad_y = float(spec["spacing"]["chip_pad_y"])
    gap = float(spec["spacing"]["sibling_gap"])
    nodes: list[Node] = []
    y = 0.0
    for index, label in enumerate(labels):
        fitted = fit_text(scene, label, "chip", column.w - 2 * pad_x, max_lines=1)
        width = fitted.width + 2 * pad_x
        height = fitted.height + 2 * pad_y
        x = column.x + (column.w - width) / 2.0
        _append_chip(nodes, comp["id"], index, fitted, x, y, width, height, spec, motion, pad_x, pad_y)
        y += height + gap
    return _Block(nodes, y - gap, True)


def _card(scene, comp, column, spec, motion, decisions, zones) -> _Block:
    pad_x = float(spec["spacing"]["text_pad_x"])
    pad_y = float(spec["spacing"]["text_pad_y"])
    gap = float(spec["spacing"]["line_gap"])
    inner_w = column.w - 2 * pad_x
    title = fit_text(scene, comp.get("title") or comp["id"], "card_title", inner_w)
    _note_shrink(decisions, comp["id"], title, spec)
    parts = [title]
    body = None
    if comp.get("body"):
        body = fit_text(scene, comp["body"], "body", inner_w)
        _note_shrink(decisions, comp["id"] + " body", body, spec)
        parts.append(body)
    text_h = sum(part.height for part in parts) + gap * (len(parts) - 1)
    width = column.w
    height = text_h + 2 * pad_y
    rect = Rect(column.x, 0.0, width, height)
    inner = Rect(rect.x + pad_x, rect.y + pad_y, inner_w, text_h)
    nodes = [Node(
        comp["id"], "card", "STAGE", rect, inner, _z(spec, "containers"),
        motion=motion, color="cyan", stroke=float(spec["spacing"]["stroke"]),
    )]
    cursor_y = inner.y
    title_inner = Rect(inner.x, cursor_y, inner.w, title.height)
    nodes.extend(_text_nodes(comp["id"], "STAGE", title, title_inner, _z(spec, "text"), "ink", motion))
    if body is not None:
        body_inner = Rect(inner.x, cursor_y + title.height + gap, inner.w, body.height)
        nodes.extend(_text_nodes(comp["id"], "STAGE", body, body_inner, _z(spec, "text"), "ink_dim", motion))
    return _Block(nodes, height, True)


def _stat(scene, comp, column, spec, motion, decisions, zones) -> _Block:
    pad_x = float(spec["spacing"]["text_pad_x"])
    pad_y = float(spec["spacing"]["text_pad_y"])
    gap = float(spec["spacing"]["line_gap"])
    inner_w = column.w - 2 * pad_x
    value = comp.get("value") or "0"
    maximum = comp.get("max_value") or value
    fitted_max = fit_text(scene, maximum, "stat", inner_w, max_lines=1)
    fitted = fit_text(scene, value, "stat", inner_w, max_lines=1)
    # Reserve the wider string so a later frame cannot change the slot.
    width = max(fitted.width, fitted_max.width)
    label = None
    label_h = 0.0
    if comp.get("title"):
        label = fit_text(scene, comp["title"], "body", inner_w)
        label_h = label.height + gap
    box_w = max(width, label.width if label is not None else 0.0)
    height = fitted.height + label_h + 2 * pad_y
    rect = Rect(column.cx - (box_w + 2 * pad_x) / 2.0, 0.0, box_w + 2 * pad_x, height)
    reserve = Rect(rect.x + pad_x, rect.y + pad_y, box_w, fitted.height)
    nodes = [Node(
        comp["id"], "stat", "STAGE", rect, Rect(rect.x + pad_x, rect.y + pad_y, box_w, height - 2 * pad_y),
        _z(spec, "containers"), motion=motion, color="yellow", stroke=float(spec["spacing"]["stroke"]),
        role="counter",
    )]
    nodes.extend(_text_nodes(comp["id"], "STAGE", fitted, reserve, _z(spec, "text"), "yellow", motion, role="counter"))
    if label is not None:
        label_inner = Rect(rect.x + pad_x, reserve.bottom + gap, box_w, label.height)
        nodes.extend(_text_nodes(comp["id"], "STAGE", label, label_inner, _z(spec, "text"), "ink_dim", motion))
    return _Block(nodes, height, True)


def _chart(scene, comp, column, spec, motion, decisions, zones) -> _Block:
    pad = float(spec["spacing"]["s"])
    tick_gap = float(spec["spacing"]["tick_gap"])
    plot_h = float(spec["blocks"]["chart_h_fraction"]) * zones.rect("STAGE").h
    y_labels = list(comp.get("y_labels") or [])
    x_labels = list(comp.get("x_labels") or [])
    title = None
    title_h = 0.0
    if comp.get("title"):
        title = fit_text(scene, comp["title"], "card_title", column.w - 2 * pad)
        title_h = title.height + pad
    y_fitted = []
    y_w = 0.0
    for label in y_labels:
        fitted = fit_text(scene, label, "body", column.w * 0.3, max_lines=1)
        y_fitted.append(fitted)
        y_w = max(y_w, fitted.width)
    if y_fitted:
        y_w += tick_gap
    x_fitted = [fit_text(scene, label, "body", column.w / max(1, len(x_labels)), max_lines=1) for label in x_labels]
    x_h = (max((item.height for item in x_fitted), default=0.0) + tick_gap) if x_fitted else 0.0
    plot = Rect(column.x + y_w, title_h, column.w - y_w, plot_h)
    height = title_h + plot_h + x_h
    outer = Rect(column.x, 0.0, column.w, height)
    nodes = [Node(
        comp["id"], comp["type"], "STAGE", outer, outer, _z(spec, "containers"),
        motion=motion, color="cyan", stroke=float(spec["spacing"]["stroke"]),
    )]
    if title is not None:
        title_inner = Rect(column.x, 0.0, column.w, title.height)
        nodes.extend(_text_nodes(comp["id"], "STAGE", title, title_inner, _z(spec, "text"), "ink", motion))
    series = list(comp.get("series") or [0, 1])
    lo = min(series)
    hi = max(series)
    span = hi - lo or 1.0
    points = []
    for index, value in enumerate(series):
        tx = plot.x + plot.w * (index / max(1, len(series) - 1))
        ty = plot.bottom - plot.h * ((value - lo) / span)
        points.append((tx, ty))
    nodes.append(Node(
        f"{comp['id']}.series", "series", "STAGE", plot, plot, _z(spec, "content"),
        parent=comp["id"], points=tuple(points), color="cyan", motion=motion,
        stroke=float(spec["spacing"]["stroke"]),
        role="bar" if comp["type"] == "bar_chart" else "line",
    ))
    _axis_labels(
        nodes, comp, spec, motion, x_fitted, y_fitted, plot, tick_gap, scene,
        optional=bool(comp.get("optional_labels")),
    )
    return _Block(nodes, height, True)


def _axis_labels(nodes, comp, spec, motion, x_fitted, y_fitted, plot, tick_gap, scene, optional: bool) -> None:
    if x_fitted:
        label_h = max(item.height for item in x_fitted)
        xaxis = Rect(plot.x, plot.bottom + tick_gap, plot.w, label_h)
        nodes.append(Node(
            f"{comp['id']}.xaxis", "axis", "STAGE", xaxis, xaxis, _z(spec, "content"),
            parent=comp["id"], role="axis", color="ink_dim", motion=motion,
        ))
        step = plot.w / max(1, len(x_fitted) - 1) if len(x_fitted) > 1 else 0.0
        previous = None
        for index, fitted in enumerate(x_fitted):
            if len(x_fitted) == 1:
                x = plot.cx - fitted.width / 2.0
            elif index == 0:
                x = plot.x
            elif index == len(x_fitted) - 1:
                x = plot.right - fitted.width
            else:
                x = plot.x + step * index - fitted.width / 2.0
            rect = Rect(x, xaxis.y, fitted.width, fitted.height)
            if rect.x < xaxis.x - 0.5 or rect.right > xaxis.right + 0.5:
                if optional:
                    continue
                raise LayoutError(
                    scene, "LR-08",
                    f"tick label {fitted.lines[0]!r} runs past the axis",
                    "Shorten the tick label or mark it optional in the DSL.",
                )
            if previous is not None and rect.gap(previous) < spec["spacing"]["chip_gap"]:
                if optional:
                    continue
                raise LayoutError(
                    scene, "LR-08",
                    f"tick label {fitted.lines[0]!r} collides with the previous tick",
                    "Drop alternate labels by marking them optional, or shorten them.",
                )
            tick_x = plot.x if index == 0 else (plot.right if index == len(x_fitted) - 1 else plot.x + step * index)
            tick_w = float(spec["spacing"]["stroke"])
            tick = Rect(
                min(tick_x, plot.right - tick_w),
                plot.bottom - spec["spacing"]["xs"],
                tick_w,
                spec["spacing"]["xs"],
            )
            nodes.append(Node(
                f"{comp['id']}.tick{index}", "tick", "STAGE", tick, tick, _z(spec, "content"),
                parent=comp["id"], role="tick", color="ink_dim", motion=motion,
            ))
            node_id = f"{comp['id']}.xlabel{index}"
            nodes.append(Node(
                node_id, "tick_label", "STAGE", rect, rect, _z(spec, "text"),
                parent=f"{comp['id']}.xaxis", role="tick_label", motion=motion,
            ))
            nodes.extend(_text_nodes(node_id, "STAGE", fitted, rect, _z(spec, "text"), "ink_dim", motion))
            previous = rect
    if y_fitted:
        top = plot.y
        yaxis = Rect(plot.x - tick_gap - max(item.width for item in y_fitted), top, tick_gap + max(item.width for item in y_fitted), plot.h)
        nodes.append(Node(
            f"{comp['id']}.yaxis", "axis", "STAGE", yaxis, yaxis, _z(spec, "content"),
            parent=comp["id"], role="axis", color="ink_dim", motion=motion,
        ))
        for index, fitted in enumerate(y_fitted):
            span = max(0.0, plot.h - fitted.height)
            if len(y_fitted) == 1:
                y = plot.y + span / 2.0
            else:
                y = plot.bottom - fitted.height - span * (index / (len(y_fitted) - 1))
            rect = Rect(yaxis.x, y, fitted.width, fitted.height)
            node_id = f"{comp['id']}.ylabel{index}"
            nodes.append(Node(
                node_id, "tick_label", "STAGE", rect, rect, _z(spec, "text"),
                parent=f"{comp['id']}.yaxis", role="tick_label", motion=motion,
            ))
            nodes.extend(_text_nodes(node_id, "STAGE", fitted, rect, _z(spec, "text"), "ink_dim", motion))


def _timeline(scene, comp, column, spec, motion, decisions, zones) -> _Block:
    ticks = list(comp.get("ticks") or [])
    if len(ticks) < 2:
        raise LayoutError(scene, "LR-08", f"{comp['id']} needs two timeline ticks", "Add the first and last tick in the DSL.")
    fitted = [fit_text(scene, tick["label"], "body", column.w * 0.45, max_lines=1) for tick in ticks]
    tick_gap = float(spec["spacing"]["tick_gap"])
    axis_y = max(item.height for item in fitted) + tick_gap
    # Labels sit under the axis. First is left-aligned, last is right-aligned.
    label_h = max(item.height for item in fitted)
    height = axis_y + tick_gap + label_h
    title_h = 0.0
    title = None
    if comp.get("title"):
        title = fit_text(scene, comp["title"], "card_title", column.w)
        title_h = title.height + spec["spacing"]["s"]
        height += title_h
        axis_y += title_h
    axis_h = float(spec["spacing"]["stroke"])
    axis = Rect(column.x, axis_y, column.w, axis_h)
    outer = Rect(column.x, 0.0, column.w, axis_y + axis_h + tick_gap + label_h)
    nodes = [Node(
        comp["id"], "timeline", "STAGE", outer, outer, _z(spec, "containers"),
        motion=motion, color="ink_dim", stroke=float(spec["spacing"]["stroke"]),
    )]
    if title is not None:
        nodes.extend(_text_nodes(comp["id"], "STAGE", title, Rect(column.x, 0.0, column.w, title.height), _z(spec, "text"), "ink", motion))
    nodes.append(Node(
        f"{comp['id']}.axis", "axis", "STAGE", axis, axis, _z(spec, "content"),
        parent=comp["id"], role="axis", color="ink_dim", motion=motion, fill=True,
    ))
    previous = None
    for index, (tick, item) in enumerate(zip(ticks, fitted)):
        if index == 0:
            x = axis.x
            tick_x = axis.x
        elif index == len(ticks) - 1:
            x = axis.right - item.width
            tick_x = axis.right
        else:
            tx = axis.x + axis.w * (index / (len(ticks) - 1))
            x = tx - item.width / 2.0
            tick_x = tx
        rect = Rect(x, axis.bottom + tick_gap, item.width, item.height)
        if rect.x < axis.x - 0.5 or rect.right > axis.right + 0.5:
            if tick.get("optional"):
                continue
            raise LayoutError(scene, "LR-08", f"{tick['label']!r} runs past the axis", "Shorten the tick label.")
        if previous is not None and rect.gap(previous) < spec["spacing"]["chip_gap"]:
            if tick.get("optional"):
                continue
            raise LayoutError(scene, "LR-08", f"{tick['label']!r} collides with another tick", "Mark alternate ticks optional or shorten them.")
        mark = Rect(
            min(tick_x, axis.right - spec["spacing"]["stroke"]),
            axis.y - spec["spacing"]["xs"],
            spec["spacing"]["stroke"],
            spec["spacing"]["xs"],
        )
        nodes.append(Node(
            f"{comp['id']}.mark{index}", "tick", "STAGE", mark, mark, _z(spec, "content"),
            parent=comp["id"], role="tick", color="cyan", motion=motion, fill=True,
        ))
        node_id = f"{tick['id']}"
        nodes.append(Node(
            node_id, "tick_label", "STAGE", rect, rect, _z(spec, "text"),
            parent=comp["id"], role="tick_label", motion=motion,
        ))
        nodes.extend(_text_nodes(node_id, "STAGE", item, rect, _z(spec, "text"), "ink", motion))
        previous = rect
    return _Block(nodes, outer.h, True)


def _flow(scene, comp, column, spec, motion, decisions, zones) -> _Block:
    steps = list(comp.get("steps") or [])
    gap = float(spec["spacing"]["sibling_gap"])
    nodes: list[Node] = []
    y = 0.0
    ids = []
    for step in steps:
        block = _card(scene, {"id": step["id"], "title": step["label"]}, column, spec, motion, decisions, zones)
        block.shift(y)
        nodes.extend(block.nodes)
        ids.append(step["id"])
        y += block.height + gap
    for left, right in zip(ids, ids[1:]):
        comp_conn = {"id": f"{left}_{right}", "from": left, "to": right, "route": "orthogonal"}
        # Routed after the stack shift, so only record the request on the parent via points later.
        nodes.append(Node(
            comp_conn["id"], "connector_request", "STAGE", Rect(0, 0, 0, 0), Rect(0, 0, 0, 0),
            _z(spec, "connectors"), text=f"{left}|{right}", motion=motion,
        ))
    height = y - gap if steps else 0.0
    return _Block(nodes, height, True)


def _hub(scene, comp, column, spec, motion, decisions, zones) -> _Block:
    spokes = list(comp.get("spokes") or [])
    if len(spokes) > int(spec["rules"]["max_chips"]):
        raise LayoutError(scene, "LR-13", "too many spokes", "Use at most four spokes.")
    hub = _card(scene, {"id": comp["id"], "title": comp.get("title") or comp["id"]}, column, spec, motion, decisions, zones)
    chips = _chips(
        scene,
        {"id": comp["id"] + ".spokes", "labels": [item["label"] for item in spokes], "alternate": "vertical"},
        column, spec, motion, decisions, zones,
    )
    gap = float(spec["spacing"]["l"])
    chips.shift(hub.height + gap)
    nodes = hub.nodes + chips.nodes
    for spoke, label_node in zip(spokes, [node for node in nodes if node.kind == "chip"]):
        nodes.append(Node(
            f"{comp['id']}.{spoke['id']}", "connector_request", "STAGE",
            Rect(0, 0, 0, 0), Rect(0, 0, 0, 0), _z(spec, "connectors"),
            text=f"{comp['id']}|{label_node.id}", motion=motion,
        ))
    height = max(node.rect.bottom for node in nodes)
    return _Block(nodes, height, True)


def _code(scene, comp, column, spec, motion, decisions, zones) -> _Block:
    pad_x = float(spec["spacing"]["text_pad_x"])
    pad_y = float(spec["spacing"]["text_pad_y"])
    gap = float(spec["spacing"]["line_gap"])
    lines = list(comp.get("lines") or [" "])
    fitted = []
    for line in lines:
        fitted.append(fit_text(scene, line, "mono", column.w - 2 * pad_x, max_lines=1))
    text_h = sum(item.height for item in fitted) + gap * (len(fitted) - 1)
    height = text_h + 2 * pad_y
    rect = Rect(column.x, 0.0, column.w, height)
    inner = Rect(rect.x + pad_x, rect.y + pad_y, rect.w - 2 * pad_x, text_h)
    nodes = [Node(
        comp["id"], "code_panel", "STAGE", rect, inner, _z(spec, "containers"),
        motion=motion, color="ink_dim", stroke=float(spec["spacing"]["stroke"]), fill=True,
    )]
    y = inner.y
    for index, item in enumerate(fitted):
        line_inner = Rect(inner.x, y, inner.w, item.height)
        nodes.extend(_text_nodes(comp["id"], "STAGE", item, line_inner, _z(spec, "text"), "green", motion))
        y += item.height + gap
    return _Block(nodes, height, True)


def _meter(scene, comp, column, spec, motion, decisions, zones) -> _Block:
    pad_y = float(spec["spacing"]["text_pad_y"])
    track_h = float(spec["blocks"]["meter_track"])
    score = float(comp.get("score") or 0)
    maximum = float(comp.get("score_max") or 10)
    label = comp.get("score_label") or f"{score:.1f}"
    reserve = comp.get("max_value") or label
    fitted = fit_text(scene, label, "mono", column.w, max_lines=1)
    fit_text(scene, reserve, "mono", column.w, max_lines=1)
    title = None
    title_h = 0.0
    if comp.get("title"):
        title = fit_text(scene, comp["title"], "card_title", column.w)
        title_h = title.height + spec["spacing"]["s"]
    height = title_h + fitted.height + pad_y + track_h
    outer = Rect(column.x, 0.0, column.w, height)
    nodes = [Node(
        comp["id"], "severity_meter", "STAGE", outer, outer, _z(spec, "containers"),
        motion=motion, color="yellow", role="counter",
    )]
    if title is not None:
        nodes.extend(_text_nodes(comp["id"], "STAGE", title, Rect(column.x, 0.0, column.w, title.height), _z(spec, "text"), "ink", motion))
    value_inner = Rect(column.x, title_h, max(fitted.width, measure(reserve, fitted.font_key, fitted.size).width), fitted.height)
    nodes.extend(_text_nodes(comp["id"], "STAGE", fitted, value_inner, _z(spec, "text"), "yellow", motion, role="counter"))
    track = Rect(column.x, title_h + fitted.height + pad_y, column.w, track_h)
    fill_w = max(spec["spacing"]["xs"], column.w * max(0.0, min(1.0, score / maximum)))
    nodes.append(Node(
        comp["id"] + ".track", "meter", "STAGE", track, track, _z(spec, "content"),
        parent=comp["id"], color="ink_dim", motion=motion, fill=True,
    ))
    nodes.append(Node(
        comp["id"] + ".fill", "meter", "STAGE", Rect(track.x, track.y, fill_w, track.h),
        Rect(track.x, track.y, fill_w, track.h), _z(spec, "content"),
        parent=comp["id"], color="yellow", motion=motion, fill=True,
    ))
    return _Block(nodes, height, True)


def _checklist(scene, comp, column, spec, motion, decisions, zones) -> _Block:
    items = list(comp.get("items") or [])
    gap = float(spec["spacing"]["sibling_gap"])
    nodes: list[Node] = []
    y = 0.0
    for index, item in enumerate(items):
        block = _card(scene, {"id": f"{comp['id']}.{index}", "title": item}, column, spec, motion, decisions, zones)
        block.shift(y)
        nodes.extend(block.nodes)
        y += block.height + gap
    height = y - gap if items else 0.0
    return _Block(nodes, height, True)


def _comparison(scene, comp, column, spec, motion, decisions, zones) -> _Block:
    gap = float(spec["spacing"]["sibling_gap"])
    side_w = (column.w - gap) / 2.0
    left_col = Rect(column.x, column.y, side_w, column.h)
    right_col = Rect(column.x + side_w + gap, column.y, side_w, column.h)
    try:
        left = _card(scene, {"id": comp["id"] + ".l", **(comp.get("left") or {})}, left_col, spec, motion, decisions, zones)
        right = _card(scene, {"id": comp["id"] + ".r", **(comp.get("right") or {})}, right_col, spec, motion, decisions, zones)
    except LayoutError:
        if comp.get("alternate") != "stack":
            raise
        decisions.append(Decision("alternate", f"{comp['id']} comparison stacked vertically"))
        left = _card(scene, {"id": comp["id"] + ".l", **(comp.get("left") or {})}, column, spec, motion, decisions, zones)
        right = _card(scene, {"id": comp["id"] + ".r", **(comp.get("right") or {})}, column, spec, motion, decisions, zones)
        right.shift(left.height + gap)
        return _Block(left.nodes + right.nodes, left.height + gap + right.height, True)
    height = max(left.height, right.height)
    return _Block(left.nodes + right.nodes, height, True)


def _grow(scene, blocks: list[_Block], column: Rect, spec, motion, decisions) -> list[_Block]:
    if not blocks:
        raise LayoutError(scene, "LR-10", "the stage is empty", "Add one stage component.")
    gap = float(spec["spacing"]["sibling_gap"])
    stage_h = column.h
    total = sum(block.height for block in blocks) + gap * (len(blocks) - 1)
    target = float(spec["rules"]["flex_target"]) * stage_h
    fail_at = float(spec["rules"]["stage_fill_fail"]) * stage_h
    if total > stage_h:
        raise LayoutError(
            scene, "LR-10",
            f"stage content is {total:.0f}px and the stage is {stage_h:.0f}px",
            "Remove a stage component or mark the scene splittable with a longer narration.",
        )
    growers = [block for block in blocks if block.flex]
    if total + 0.5 < target and growers:
        extra = target - total
        share = extra / len(growers)
        for block in growers:
            _append_figures(block, share, column, spec, motion)
        decisions.append(Decision("reflow", f"illustrations grew by {extra:.0f}px to fill the stage"))
        total = sum(block.height for block in blocks) + gap * (len(blocks) - 1)
    if total + 0.5 < fail_at:
        raise LayoutError(
            scene, "LR-10",
            f"stage content fills {total / stage_h:.0%} of the stage",
            "Add an illustration component or allow the template figure to grow. Do not leave the stage empty.",
        )
    if total < target:
        decisions.append(Decision(
            "warn",
            f"LR-10 stage fill {total / stage_h:.0%} is between the fail and warn lines",
        ))
    return blocks


def _drawn(nodes: list[Node]) -> list[Node]:
    return [node for node in nodes if node.kind != "connector_request"]


def _append_figures(block: _Block, extra: float, column: Rect, spec, motion) -> None:
    if extra < 1:
        return
    drawn = _drawn(block.nodes)
    bar_h = float(spec["spacing"]["l"])
    gap = float(spec["spacing"]["sibling_gap"])
    bottom = max(node.rect.bottom for node in drawn)
    left = min(node.rect.x for node in drawn)
    width = max(node.rect.right for node in drawn) - left
    stem = drawn[0].id
    y = bottom + gap
    remaining = extra - gap
    index = 0
    while remaining >= bar_h:
        rect = Rect(left, y, width, bar_h)
        block.nodes.append(Node(
            f"{stem}.figure.{index}", "figure", "STAGE", rect, rect, _z(spec, "content"),
            color="cyan", fill=True, motion=motion,
        ))
        y += bar_h + gap
        remaining -= bar_h + gap
        index += 1
    if remaining > 1:
        rect = Rect(left, y, width, remaining)
        block.nodes.append(Node(
            f"{stem}.figure.{index}", "figure", "STAGE", rect, rect, _z(spec, "content"),
            color="cyan", fill=True, motion=motion,
        ))
    drawn = _drawn(block.nodes)
    block.height = max(node.rect.bottom for node in drawn) - min(node.rect.y for node in drawn)


def _stack(scene, blocks: list[_Block], column: Rect, spec) -> None:
    gap = float(spec["spacing"]["sibling_gap"])
    total = sum(block.height for block in blocks) + gap * (len(blocks) - 1)
    y = column.y + (column.h - total) / 2.0
    for block in blocks:
        top = min(node.rect.y for node in _drawn(block.nodes))
        block.shift(y - top)
        y += block.height + gap
    # Internal gaps larger than the token are a balance failure.
    ceilings = []
    for block in blocks:
        ceilings.append((
            min(n.rect.y for n in _drawn(block.nodes)),
            max(n.rect.bottom for n in _drawn(block.nodes)),
        ))
    ceilings.sort()
    limit = float(spec["spacing"]["max_stack_gap"])
    for (a_top, a_bot), (b_top, b_bot) in zip(ceilings, ceilings[1:]):
        if b_top - a_bot > limit + 0.5:
            raise LayoutError(
                scene, "LR-10",
                f"empty gap of {b_top - a_bot:.0f}px inside the stage stack",
                "Bring the stage components together. Large empty holes in the stack are not allowed.",
            )


def _overlay(doc, nodes, column, spec, motion, zones) -> list[Node]:
    size = float(spec["spacing"]["l"])
    gap = float(spec["spacing"]["sibling_gap"])
    candidates = [
        Rect(column.x, column.y, size, size),
        Rect(column.right - size, column.y, size, size),
        Rect(column.x, column.bottom - size, size, size),
        Rect(column.right - size, column.bottom - size, size, size),
    ]
    text_boxes = [node.rect.inflate(gap) for node in nodes if node.kind == "text" or node.role == "icon"]
    for rect in candidates:
        if zones.contains("STAGE", rect) and all(not rect.intersects(box) for box in text_boxes):
            return [Node(
                doc["overlay"]["id"], "cursor", "STAGE", rect, rect, _z(spec, "overlays"),
                role="overlay", color="yellow", motion=motion, fill=True,
            )]
    raise LayoutError(
        doc["id"], "LR-11",
        "the cursor has no empty slot that avoids text",
        "Remove the cursor or remove a stage component so a corner stays clear.",
    )


def _connectors(doc, nodes: list[Node], zones: ZoneMap, spec) -> None:
    requests = [node for node in nodes if node.kind == "connector_request"]
    for item in list(doc.get("connectors") or []):
        requests.append(Node(
            item["id"], "connector_request", "STAGE", Rect(0, 0, 0, 0), Rect(0, 0, 0, 0),
            _z(spec, "connectors"), text=f"{item['from']}|{item['to']}",
        ))
    if not requests:
        return
    by_id = {node.id: node for node in nodes}
    obstacles = [
        node.ink.inflate(spec["spacing"]["connector_inflate"])
        for node in nodes
        if node.ink is not None
    ]
    bounds = zones.stage_column().inflate(spec["spacing"]["s"])
    built = []
    for request in requests:
        left_id, _, right_id = request.text.partition("|")
        if left_id not in by_id or right_id not in by_id:
            raise LayoutError(
                doc["id"], "LR-06",
                f"connector {request.id} points at a missing component",
                "Connectors must name component ids that exist in this scene.",
            )
        start, end = anchors(by_id[left_id].rect, by_id[right_id].rect)
        points = route(
            doc["id"], start, end, obstacles, bounds, int(spec["grid"]),
            mode="orthogonal",
        )
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        box = Rect(min(xs), min(ys), max(xs) - min(xs) or 1, max(ys) - min(ys) or 1)
        built.append(Node(
            request.id if request.id else f"{left_id}_{right_id}",
            "connector", "STAGE", box, box, _z(spec, "connectors"),
            points=points, color="cyan", stroke=float(spec["spacing"]["stroke"]),
            glow=float(spec["spacing"]["glow_bleed"]), motion=request.motion,
        ))
    nodes[:] = [node for node in nodes if node.kind != "connector_request"]
    nodes.extend(built)


def _assert_inside(scene: str, nodes: list[Node], zones: ZoneMap) -> None:
    for node in nodes:
        if node.kind == "connector":
            continue
        visual = node.rect.inflate(node.glow)
        if not zones.contains(node.zone, visual):
            raise LayoutError(
                scene, "LR-01",
                f"{node.id} leaves the {node.zone} zone",
                "Shorten this component or move it into its own scene.",
                element=node.id,
            )


def _shift_node(node: Node, dy: float) -> Node:
    ink = None if node.ink is None else Rect(node.ink.x, node.ink.y + dy, node.ink.w, node.ink.h)
    return replace(
        node,
        rect=Rect(node.rect.x, node.rect.y + dy, node.rect.w, node.rect.h),
        content=Rect(node.content.x, node.content.y + dy, node.content.w, node.content.h),
        ink=ink,
        points=tuple((x, y + dy) for x, y in node.points),
    )
