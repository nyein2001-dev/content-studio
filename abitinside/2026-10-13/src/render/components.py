#!/usr/bin/env python3
"""
A Bit Inside - reusable on-screen components.

Every one of these draws vector geometry only: rounded pills and cards, wordmark,
headline, underline, burned-in captions, counters, meters, the cold-chain trace,
the store elevation, the controller box and the dot grids.

Colours come from theme's semantic roles (SUBJECT/NUMBER/PROBLEM/SUCCESS), never
from raw hex at the call site.
"""
from __future__ import annotations

import math

import cairo

import theme as T
from engine import (Text, dashed_rect, fill_colour, line, paint_glow, rrect,
                    stroke_colour)

CAP_RATIO = 0.70          # Poppins cap height / em


# ---------------------------------------------------------------- brand
def wordmark(cr: cairo.Context, txt: Text, alpha: float = 1.0,
             pop: float = 1.0) -> None:
    """Cyan bar + 'A Bit Inside', centred on x=540 at the measured y=250."""
    s = T.SIZE_WORDMARK
    txt.font("pop", s, "bold")
    label = "A Bit Inside"
    tw = txt.width(label)
    bw = T.WORDMARK_BAR_W * pop
    gap = T.WORDMARK_GAP
    total = bw + gap + tw
    x0 = T.CENTER_X - total / 2
    y = T.WORDMARK_Y
    h = T.WORDMARK_BAR_H * (2 * T.ease_out_back(pop) - 1) if pop < 1 else T.WORDMARK_BAR_H
    rrect(cr, x0, y - h / 2, bw, h, bw / 2)
    fill_colour(cr, T.CYAN, alpha)
    cr.new_path()
    txt.draw(x0 + bw + gap, y + s * 0.355, label, T.INK, alpha)


# ---------------------------------------------------------------- headline
def headline(cr: cairo.Context, txt: Text, lines, frame: float, a: float, b: float,
             colour: str = T.CYAN, alpha: float = 1.0) -> None:
    """Slide-up + fade over HEADLINE_IN frames, ease-out cubic. Underline draws on.

    The entrance starts HEADLINE_IN/2 frames BEFORE the scene boundary so that
    frame 1 already carries the hook claim while still moving, as the spec
    requires.
    """
    lead = T.HEADLINE_IN_FRAMES / 2
    t = T.progress(frame, a - lead, a + lead)
    e = T.ease_out_cubic(t)
    if t <= 0:
        return
    out = T.progress(frame, b - T.HEADLINE_OUT_FRAMES, b)
    fade = alpha * (1.0 - T.ease_in_out_cubic(out))
    if fade <= 0.01:
        return
    size = T.SIZE_HEADLINE
    txt.font("pop", size, "bold")
    dy = (1.0 - e) * 34
    base1 = T.HEADLINE_TOP + CAP_RATIO * size + dy
    pitch = T.HEADLINE_LINE_PITCH
    widths = [txt.width(l) for l in lines]
    for i, line_txt in enumerate(lines):
        base = base1 + i * pitch
        runs = [(line_txt, T.INK)]
        txt.runs(T.CENTER_X, base, runs, fade, align="center")

    # short coloured underline, drawn on just after the text
    ut = T.ease_out_cubic(T.progress(frame, a - 4, a + T.HEADLINE_IN_FRAMES))
    if ut > 0 and lines:
        last = lines[-1]
        wmax = max(widths) * 1.0
        ux0 = T.CENTER_X - T.UNDERLINE_W / 2
        uy = T.UNDERLINE_Y + dy
        cr.rectangle(ux0, uy, T.UNDERLINE_W * ut, T.UNDERLINE_H)
        fill_colour(cr, colour, fade)
        cr.new_path()


# ---------------------------------------------------------------- captions
def caption(txt: Text, group: dict, frame: float, scene_end: int) -> list | None:
    """Return the runs for the caption visible at `frame`, or None."""
    if not (group["frame"] <= frame < group["end_frame"]):
        return None
    t = T.progress(frame, group["frame"], group["frame"] + T.CAPTION_IN_FRAMES)
    e = T.ease_out_cubic(t)
    words = group["text"].split()
    key = group.get("key", "")
    accent = group.get("accent", "yellow")
    colour = T.CYAN if accent == "cyan" else T.YELLOW
    return words, key, colour, e, frame


def draw_caption(cr: cairo.Context, txt: Text, c, alpha: float = 1.0) -> None:
    """Delegate to the shared caption painter. Day code must not draw words itself."""
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from pipeline.captions import visible_runs

    frame = c[4] if isinstance(c, tuple) else c.get("frame", 0)
    group = c if isinstance(c, dict) else None
    if group is None:
        return
    runs, ease = visible_runs(group, frame)
    if not runs:
        return
    txt.font("pop", T.SIZE_CAPTION, "bold")
    total = sum(txt.width(piece) for piece, _colour in runs)
    x = T.CENTER_X - total / 2 + (1 - ease) * 18
    y = T.CAPTION_CENTER_Y + T.SIZE_CAPTION * 0.70 * 0.5 + (1 - ease) * 12
    txt.runs(x, y, runs, alpha, align="left")


# ---------------------------------------------------------------- primitives
def pill(cr: cairo.Context, txt: Text, cx: float, cy: float, label: str,
         colour: str = T.CYAN, size: float = T.SIZE_PILL, alpha: float = 1.0,
         fill: bool = False) -> tuple[float, float]:
    txt.font("pop", size, "bold")
    w = txt.width(label)
    padx, pady = size * 0.62, size * 0.42
    bw, bh = w + padx * 2, size + pady * 2
    x, y = cx - bw / 2, cy - bh / 2
    if fill:
        rrect(cr, x, y, bw, bh, bh / 2)
        fill_colour(cr, colour, alpha * 0.16)
        cr.new_path()
    rrect(cr, x, y, bw, bh, bh / 2)
    stroke_colour(cr, colour, T.STROKE, alpha)
    txt.draw(cx - w / 2, cy + size * CAP_RATIO * 0.5, label, colour, alpha)
    return bw, bh


def card(cr: cairo.Context, txt: Text, x: float, y: float, w: float, h: float,
         label: str = "", sub: str = "", colour: str = T.CYAN,
         alpha: float = 1.0, dashed: bool = False) -> None:
    r = 22
    if dashed:
        rrect(cr, x, y, w, h, r)
        stroke_colour(cr, colour, T.STROKE, alpha * 0.75)
        cr.set_dash([])
    else:
        rrect(cr, x, y, w, h, r)
        fill_colour(cr, colour, alpha * 0.10)
        cr.new_path()
        rrect(cr, x, y, w, h, r)
        stroke_colour(cr, colour, T.STROKE, alpha)
    if label:
        txt.font("pop", T.SIZE_LABEL, "bold")
        txt.draw_c(x + w / 2, y + h * (0.42 if sub else 0.56), label, T.INK, alpha)
    if sub:
        txt.font("pop", 34, "bold")
        txt.draw_c(x + w / 2, y + h * 0.76, sub, colour, alpha * 0.95)


def big_number(cr: cairo.Context, txt: Text, cx: float, base: float, value: str,
               colour: str = T.NUMBER, size: float = T.SIZE_BIG_NUM,
               alpha: float = 1.0) -> None:
    txt.font("pop", size, "bold")
    txt.draw_c(cx, base, value, colour, alpha)


def meter(cr: cairo.Context, txt: Text, x: float, y: float, w: float, h: float,
          frac: float, colour: str = T.SUBJECT, label: str = "",
          value_text: str = "", alpha: float = 1.0) -> None:
    rrect(cr, x, y, w, h, h / 2)
    fill_colour(cr, T.INK, alpha * 0.10)
    cr.new_path()
    fw = max(h, w * T.clamp01(frac))
    if fw > h:
        rrect(cr, x, y, fw, h, h / 2)
        fill_colour(cr, colour, alpha)
        cr.new_path()
    rrect(cr, x, y, w, h, h / 2)
    stroke_colour(cr, colour, T.STROKE, alpha * 0.85)
    if label:
        txt.font("pop", 34, "bold")
        txt.draw(x, y - 18, label, T.INK_DIM, alpha)
    if value_text:
        txt.font("pop", 40, "bold")
        txt.draw_r(x + w, y - 18, value_text, colour, alpha)


# ---------------------------------------------------------------- domain art
def controller_box(cr: cairo.Context, txt: Text, cx: float, cy: float, scale: float,
                   label: str = "CONTROLLER", colour: str = T.CYAN,
                   alpha: float = 1.0, glow_on: float = 0.0) -> tuple[float, float]:
    """The AK-SM style supervisory controller: a small box with three indicator
    lights and a management port. Entirely schematic, labelled ILLUSTRATIVE by the
    scene, never a photograph of a real device."""
    w, h = 300 * scale, 200 * scale
    x, y = cx - w / 2, cy - h / 2
    if glow_on > 0:
        paint_glow(cr, cx, cy, int(300 * scale), colour, 0.45 * glow_on)
    rrect(cr, x, y, w, h, 18 * scale)
    fill_colour(cr, colour, alpha * 0.10)
    cr.new_path()
    rrect(cr, x, y, w, h, 18 * scale)
    stroke_colour(cr, colour, T.STROKE, alpha)
    for i, c in enumerate((T.SUCCESS, T.NUMBER, T.PROBLEM)):
        lx = x + 34 * scale + i * 46 * scale
        cr.arc(lx, y + 44 * scale, 11 * scale, 0, 6.2832)
        fill_colour(cr, c, alpha * (0.35 + 0.65 * glow_on))
        cr.new_path()
    # ventilation slots
    for i in range(4):
        line(cr, x + 150 * scale, y + (34 + i * 16) * scale,
             x + (150 + 90) * scale, y + (34 + i * 16) * scale, colour,
             T.STROKE_THIN, alpha * 0.55)
    # management port
    rrect(cr, x + 40 * scale, y + 118 * scale, 120 * scale, 46 * scale, 8 * scale)
    stroke_colour(cr, colour, T.STROKE_THIN, alpha * 0.9)
    if label:
        txt.font("pop", 34, "bold")
        txt.draw_c(cx, y + h + 44, label, colour, alpha)
    return w, h


def chilled_case(cr: cairo.Context, x: float, y: float, w: float, h: float,
                 temp_colour: str = T.CYAN, warm: float = 0.0, alpha: float = 1.0) -> None:
    """A front-on refrigerated case with a glass door band."""
    rrect(cr, x, y, w, h, 16)
    fill_colour(cr, T.INK, alpha * 0.05)
    cr.new_path()
    rrect(cr, x, y, w, h, 16)
    stroke_colour(cr, T.INK_FAINT, T.STROKE_THIN, alpha * 0.8)
    gy = y + h * 0.18
    gh = h * 0.52
    rrect(cr, x + 12, gy, w - 24, gh, 10)
    fill_colour(cr, temp_colour, alpha * (0.16 + 0.5 * warm))
    cr.new_path()
    for i in range(3):
        line(cr, x + 34, gy + gh * (0.34 + 0.18 * i), x + 34, gy + gh * (0.34 + 0.18 * i),
             T.INK, 0, 0)
    line(cr, x + 30, gy + gh * 0.72, x + w - 30, gy + gh * 0.72, T.INK,
         T.STROKE_THIN, alpha * 0.35)


def store_elevation(cr: cairo.Context, txt: Text, alpha: float = 1.0,
                    warm: float = 0.0, box_glow: float = 0.0) -> None:
    """Side elevation of a shop: floor, four chilled cases, the controller on the
    back wall, a router outside. The recurring set piece for the whole video."""
    floor_y = 1230
    cr.rectangle(T.SAFE_X0, floor_y, T.SAFE_W, 8)
    fill_colour(cr, T.INK_FAINT, alpha * 0.45)
    cr.new_path()
    for i in range(4):
        chilled_case(cr, 165 + i * 175, floor_y - 270, 140, 262, warm=warm, alpha=alpha)
    controller_box(cr, txt, 820, floor_y - 430, 0.62, label="", alpha=alpha,
                   glow_on=box_glow)
    txt.font("pop", 34, "bold")
    txt.draw_c(820, floor_y - 330, "CONTROLLER", T.CYAN, alpha * 0.9)
    # router outside the shop
    cr.arc(172, floor_y - 400, 32, 0, 6.2832)
    fill_colour(cr, T.INK, alpha * 0.10)
    cr.new_path()
    cr.arc(150, floor_y - 400, 32, 0, 6.2832)
    stroke_colour(cr, T.INK_DIM, T.STROKE_THIN, alpha)


def dot_grid(cr: cairo.Context, x: float, y: float, cols: int, rows: int, pitch: float,
             total: int, r: float = 6.0, lit: str = T.CYAN, dim: str = T.INK_FAINT,
             alpha: float = 1.0, lit_alpha: float = 1.0) -> None:
    """One dot = one device. Used for the exposed-controller count and the store
    count, so a big number is always literally visible as many marks."""
    k = 0
    for row in range(rows):
        for col in range(cols):
            cx = x + col * pitch
            cy = y + row * pitch
            if k >= total:
                break
            cr.arc(cx, cy, r, 0, 6.2832)
            fill_colour(cr, lit, alpha * lit_alpha)
            cr.new_path()
            k += 1


def trace(cr: cairo.Context, x0: float, y0: float, x1: float, y1: float,
          lo: float, hi: float, vmin: float, vmax: float,
          attack_frame: int = -1, reveal: float = 1.0,
          colour: str = T.CYAN, band_lo: float | None = None,
          band_hi: float | None = None, alpha: float = 1.0,
          width: float = T.STROKE + 1, grid: bool = False) -> None:
    """The cold-chain trace: one polyline inside a frame, the healthy band drawn
    as a dashed corridor, the attack portion revealed up to `reveal`."""
    def px(t):
        return x0 + (x1 - x0) * t

    def py(v):
        f = (v - vmin) / max(1e-6, (vmax - vmin))
        return y1 - (y1 - y0) * T.clamp01(f)

    cr.rectangle(x0, y0, x1 - x0, y1 - y0)
    stroke_colour(cr, T.INK_FAINT, T.STROKE_THIN, alpha * 0.7)

    if grid:
        for gv in range(int(math.ceil(vmin)), int(vmax) + 1, 10):
            y = py(gv)
            cr.move_to(x0, y)
            cr.line_to(x1, y)
            stroke_colour(cr, T.INK_FAINT, 1.0, alpha * 0.25)

    if band_lo is not None and band_hi is not None:
        cr.rectangle(x0, py(band_hi), x1 - x0, py(band_lo) - py(band_hi))
        fill_colour(cr, T.SUCCESS, alpha * 0.12)
        cr.new_path()
        cr.rectangle(x0, py(band_hi), x1 - x0, py(band_lo) - py(band_hi))
        stroke_colour(cr, T.SUCCESS, T.STROKE_THIN, alpha * 0.6)

    n = 150
    has_attack = 0 <= attack_frame < n
    att_t = (attack_frame / n) if has_attack else None
    pts = []
    for i in range(n + 1):
        t = i / n
        if has_attack and t >= att_t:
            break
        v = lo + 0.35 * math.sin(t * 41.0) + 0.18 * math.sin(t * 113.0)
        pts.append((px(t), py(v)))
    if has_attack:
        pts.append((px(att_t), py(lo + 0.2)))
        m = 40
        for i in range(m + 1):
            t = att_t + i * (1.0 - att_t) / m
            u = i / m
            v = lo + 0.2 + (vmax * 0.92 - lo) * (u ** 1.7)
            pts.append((px(t), py(v)))
    if reveal < 1.0:
        cut = int(len(pts) * reveal)
        pts = pts[: max(2, cut)]
    if len(pts) < 2:
        return
    cr.move_to(*pts[0])
    for p in pts[1:]:
        cr.line_to(*p)
    stroke_colour(cr, colour, width, alpha)


def chip(cr: cairo.Context, txt: Text, x: float, y: float, label: str,
         colour: str = T.CYAN, alpha: float = 1.0, w: float | None = None,
         size: float = 36) -> None:
    txt.font("pop", size, "bold")
    ww = w if w is not None else txt.width(label) + 46
    rrect(cr, x, y, ww, size + 30, 16)
    fill_colour(cr, colour, alpha * 0.12)
    cr.new_path()
    rrect(cr, x, y, ww, size + 30, 16)
    stroke_colour(cr, colour, T.STROKE_THIN, alpha)
    txt.draw(x + ww / 2, y + size + 6, label, colour, alpha)


def illustrative(cr: cairo.Context, txt: Text, x: float, y: float,
                 alpha: float = 1.0) -> None:
    txt.font("pop", 34, "bold")
    txt.draw(x, y, "ILLUSTRATIVE", T.INK_FAINT, alpha * 0.95)


def house(cr: cairo.Context, cx: float, cy: float, scale: float, alpha: float = 1.0,
          colour: str = T.INK_DIM) -> None:
    w, h = 420 * scale, 300 * scale
    x, y = cx - w / 2, cy - h / 2
    cr.move_to(x, y + h * 0.34)
    cr.line_to(cx, y)
    cr.line_to(x + w, y + h * 0.34)
    stroke_colour(cr, colour, T.STROKE, alpha)
    rrect(cr, x, y + h * 0.34, w, h * 0.66, 12)
    stroke_colour(cr, colour, T.STROKE, alpha)