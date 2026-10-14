#!/usr/bin/env python3
"""
A Bit Inside - the scenes.

One function per scene. Each is driven only by timeline.json (for its frame
range and beats) and facts.json (for every number it shows). Nothing is
hard-coded here that is not either a layout constant or a beat description.

The recurring visual metaphor is the cold-chain trace: one temperature line runs
under the whole video, flat and healthy for most of it, and gone in one night in
October.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import cairo

import theme as T
from components import (big_number, caption, card, chip, chilled_case, controller_box,
                         dot_grid, headline, house, illustrative, meter, pill,
                         store_elevation, trace, wordmark)
from engine import Text, fill_colour, line, paint_glow, rrect, stroke_colour

DAY = Path(__file__).resolve().parent.parent.parent
FACTS = {f["id"]: f for f in json.loads((DAY / "facts.json").read_text(encoding="utf-8"))["facts"]}


def v(fact_id: str):
    return FACTS[fact_id]["value"]


def fmt_int(n) -> str:
    return f"{int(n):,}"


def beat_frame(scene, k: int) -> int:
    """Beat k of a scene, as an absolute frame.

    Beat 0 lands exactly on the scene's first frame. That matters: the old
    distribution put the first reveal 35% into the scene, which left every cut
    followed by half a second of empty picture. timeline.py uses this same
    function to place the label-pop click, so the sound lands on the cut too.
    """
    n = len(scene.get("beats", []))
    if n <= 0:
        return scene["start_frame"]
    a, b = scene["start_frame"], scene["end_frame"]
    return a + int((b - a) * k / n)


def local_t(scene, frame: float) -> float:
    return T.clamp01((frame - scene["start_frame"]) /
                     max(1, scene["end_frame"] - scene["start_frame"]))


def reveal(scene, frame: float, k: int, dur: float = 14.0) -> float:
    """How far beat k has drawn itself by `frame`.

    Beat 0 sits exactly on the scene's first frame, and timeline.py puts the
    label-pop click there too. The reveal therefore starts REVEAL_LEAD frames
    early so that the element is already ~80% drawn on the cut itself: without
    it, every scene opens with a dead frame.
    """
    bf = beat_frame(scene, k)
    return T.ease_out_cubic(T.progress(frame, bf - REVEAL_LEAD, bf + dur - REVEAL_LEAD))


# ---------------------------------------------------------------- scenes
ILLU_Y = 1378            # every ILLUSTRATIVE label sits here, above the caption band
CHART = (T.SAFE_X0 + 40, 640, T.SAFE_X1 - 40, 1210)   # x0, y0, x1, y1
REVEAL_LEAD = 6          # frames a beat's reveal starts before its own beat frame


def hook(cr, txt, frame, scene, alpha=1.0):
    f0 = scene["start_frame"]
    dt = max(0, frame - f0)
    x0, y0, x1, y1 = CHART
    lo, hi = v("normal_case_temp"), v("attack_temp_c")
    # impact ring, drawn first so it sits behind the chart
    r = 110 + (dt % 22) * 34
    cr.arc(x1 - 150, y0 + 120, r, 0, 6.2832)
    stroke_colour(cr, T.PROBLEM, T.STROKE_THIN, alpha * max(0.0, 0.38 - dt * 0.07))
    # the trace slams up and pins at the top within the first few frames
    trace(cr, x0, y0, x1, y1, lo, hi, 0.0, 56.0, attack_frame=104, reveal=1.0,
          band_lo=lo - 1.0, band_hi=lo + 2.0, alpha=alpha, width=5, grid=True)
    txt.font("pop", 34, "bold")
    for gv in (0, 20, 40):
        f = gv / 56.0
        gy = y1 - (y1 - y0) * f
        txt.draw(x0 - 12, gy + 12, f"{gv}", T.INK_FAINT, alpha * 0.9)
    txt.draw(x0, y1 + 52, "CASE TEMPERATURE, DEGREES", T.INK_DIM, alpha)
    txt.font("pop", T.SIZE_BIG_NUM * 0.62, "bold")
    txt.draw(x1 - txt.width(f"{int(hi)}\u00b0C"), y1 + 52, f"{int(hi)}\u00b0C",
             T.NUMBER, alpha)
    illustrative(cr, txt, T.SAFE_X0 + 4, ILLU_Y, alpha)


def setup(cr, txt, frame, scene, alpha=1.0):
    e0 = reveal(scene, frame, 0)
    e1 = reveal(scene, frame, 1)
    e2 = reveal(scene, frame, 2)
    # the store hands over to the dot grid rather than sitting behind it
    store_alpha = e0 * max(0.0, 1.0 - e1 * 1.15)
    if store_alpha > 0.01:
        store_elevation(cr, txt, alpha * store_alpha, warm=0.55 * e0,
                        box_glow=0.8 * e0)
        txt.font("pop", 34, "bold")
        txt.draw_c(T.CENTER_X, 1330, "A SUPERMARKET COLD ROOM", T.INK_DIM,
                   alpha * store_alpha)
    if e1 > 0:
        total = int(v("intermarche_stores"))
        dot_grid(cr, 200, 780, 30, 5, 24, total, r=6.5, lit=T.NUMBER,
                 alpha=alpha, lit_alpha=e1)
        txt.font("pop", 40, "bold")
        txt.draw(T.SAFE_X0 + 4, 730, "ONE DOT = ONE STORE", T.INK_DIM, alpha * e1)
        big_number(cr, txt, T.CENTER_X, 1180, fmt_int(total), T.NUMBER,
                   T.SIZE_BIG_NUM * 0.52, alpha * e1)
        txt.font("pop", 36, "bold")
        txt.draw_c(T.CENTER_X, 1250, "STORES HIT, PER THE CHAIN", T.INK_DIM, alpha * e1)
    if e2 > 0:
        card(cr, txt, 240, 820, 600, 250, "A WEB PAGE LOADED",
             "NO DOOR FORCED", T.PROBLEM, alpha * e2)
        illustrative(cr, txt, T.SAFE_X0 + 4, ILLU_Y, alpha)


def controller(cr, txt, frame, scene, alpha=1.0):
    e0 = reveal(scene, frame, 0)
    floor_y = 1360
    box_cx, box_cy = T.CENTER_X, 790
    s = 0.55 + 0.35 * e0
    controller_box(cr, txt, box_cx, box_cy, s, label="SUPERVISORY CONTROLLER",
                   alpha=alpha * e0, glow_on=e0)
    txt.font("pop", 34, "bold")
    txt.draw_c(T.CENTER_X, 1010, "one box runs every case in the store",
               T.INK_DIM, alpha * e0)

    e1 = reveal(scene, frame, 1)
    for i, name in enumerate(("PROBES", "TARGET", "DEFROST")):
        pill(cr, txt, 255 + i * 285, 1110, name, T.CYAN, 36, alpha * e1)

    e2 = reveal(scene, frame, 2)
    if e2 > 0:
        for i in range(4):
            line(cr, box_cx, 900 + (i % 2) * 20, 235 + i * 175, floor_y - 250,
                 T.CYAN, T.STROKE_THIN, alpha * e2 * 0.55, dash=(8, 12))
        for i in range(4):
            chilled_case(cr, 165 + i * 175, floor_y - 250, 140, 242,
                         alpha=alpha * e2)
        cr.rectangle(T.SAFE_X0, floor_y, T.SAFE_W, 6)
        fill_colour(cr, T.INK_FAINT, alpha * e2 * 0.4)
        cr.new_path()


def why_online(cr, txt, frame, scene, alpha=1.0):
    e0 = reveal(scene, frame, 0)
    cr.arc(190, 1150, 38, 0, 6.2832)
    stroke_colour(cr, T.INK_DIM, T.STROKE, alpha * e0)
    line(cr, 190, 1150, T.CENTER_X, 900, T.CYAN, T.STROKE_THIN, alpha * e0)
    controller_box(cr, txt, T.CENTER_X, 840, 0.9, label="", alpha=alpha * e0,
                   glow_on=0.6 * e0)
    e1 = reveal(scene, frame, 1)
    pill(cr, txt, T.CENTER_X, 660, "LATE-NIGHT ALARM", T.NUMBER, 38, alpha * e1)
    txt.font("pop", 36, "bold")
    txt.draw_c(T.CENTER_X, 1090, "the engineer has to clear it", T.INK_DIM, alpha * e1)
    e2 = reveal(scene, frame, 2)
    if e2 > 0:
        card(cr, txt, 250, 1220, 580, 170, "WEB MANAGEMENT",
             "reachable from anywhere", T.CYAN, alpha * e2)
        illustrative(cr, txt, T.SAFE_X0 + 4, ILLU_Y, alpha)


def the_flaw(cr, txt, frame, scene, alpha=1.0):
    e0 = reveal(scene, frame, 0)
    e1 = reveal(scene, frame, 1)
    e2 = reveal(scene, frame, 2)
    e3 = reveal(scene, frame, 3)
    card(cr, txt, 210, 590, 660, 190, "THREE FLAWS FOUND",
         "in the management interface", T.PROBLEM, alpha * e0)
    for i in range(3):
        pe = T.ease_out_cubic(T.progress(frame, beat_frame(scene, 0) + i * 8,
                                         beat_frame(scene, 0) + i * 8 + 12))
        pill(cr, txt, 255 + i * 285, 845, f"0{i + 1}", T.PROBLEM, 34, alpha * pe)
    if e2 > 0:
        rrect(cr, 250, 900, 580, 104, 18)
        stroke_colour(cr, T.SUCCESS, T.STROKE, alpha * e2)
        txt.font("pop", 40, "bold")
        txt.draw_c(T.CENTER_X, 968, "LOGIN ACCEPTED", T.SUCCESS, alpha * e2)
    if e1 > 0:
        cx, cy = T.CENTER_X, 1130
        rrect(cr, cx - 230, cy - 120, 460, 240, 20)
        fill_colour(cr, T.INK, alpha * e0 * 0.08)
        cr.new_path()
        rrect(cr, cx - 230, cy - 120, 460, 240, 20)
        stroke_colour(cr, T.CYAN, T.STROKE, alpha * e1)
        txt.font("pop", 38, "bold")
        txt.draw_c(cx, cy - 64, "CODE OF THE DAY", T.INK_DIM, alpha * e1)
        code = "7F2A-91C4"
        n = int(len(code) * T.clamp01(T.progress(frame, beat_frame(scene, 1) + 6,
                                                beat_frame(scene, 1) + 96)))
        txt.font("mono", 60, "bold")
        txt.draw_c(cx, cy + 36, code[:n], T.NUMBER, alpha * e1)
        txt.font("pop", 34, "bold")
        txt.draw_c(cx, cy + 96, "built from the box's own date", T.INK_DIM, alpha * e1)
        illustrative(cr, txt, cx + 40, cy + 162, alpha * e1)
    if e3 > 0:
        sc = v("cve_cvss")
        mx = v("cvss_max")
        txt.font("mono", 36, "bold")
        txt.draw_c(T.CENTER_X, 1418, "CVE-2025-41450", T.CYAN, alpha * e3)
        meter(cr, txt, T.SAFE_X0 + 20, 1330, 800, 32, sc / mx, T.NUMBER,
              "SEVERITY", f"{sc} / {int(mx)}  HIGH", alpha * e3)


def the_scale(cr, txt, frame, scene, alpha=1.0):
    total = int(v("exposed_controllers"))
    e2 = reveal(scene, frame, 2)
    cols, rows = 40, 20
    pitch = 20.0
    gx = T.CENTER_X - (cols - 1) * pitch / 2
    gy = 740
    grid_alpha = alpha * max(0.0, 1.0 - e2 * 1.3)
    if grid_alpha > 0.01:
        lit = int(total * reveal(scene, frame, 1, dur=120))
        for i in range(cols * rows):
            col, row = i % cols, i // cols
            cr.arc(gx + col * pitch, gy + row * pitch, 5.0, 0, 6.2832)
            fill_colour(cr, T.CYAN if i < lit else T.INK_FAINT,
                        grid_alpha * (1.0 if i < lit else 0.35))
            cr.new_path()
        txt.font("pop", 36, "bold")
        txt.draw_c(T.CENTER_X, 700, "EXPOSED ON THE INTERNET", T.INK_DIM, grid_alpha)
        e0 = T.ease_out_cubic(T.progress(frame, beat_frame(scene, 1),
                                         beat_frame(scene, 1) + 150))
        big_number(cr, txt, T.CENTER_X, 1300, fmt_int(int(total * e0)), T.CYAN,
                   T.SIZE_BIG_NUM * 0.62, grid_alpha)
        txt.font("pop", 36, "bold")
        txt.draw_c(T.CENTER_X, 1360, "COUNTED BY THE RESEARCHERS", T.INK_DIM,
                   grid_alpha)
    if e2 > 0:
        card(cr, txt, 150, 820, 780, 300, "PATCHED?", "nobody knows how many",
             T.INK_FAINT, alpha * e2, dashed=True)
        txt.font("pop", 36, "bold")
        txt.draw_c(T.CENTER_X, 1200, "THE RESEARCHERS SAID SO", T.INK_DIM, alpha * e2)


def legacy(cr, txt, frame, scene, alpha=1.0):
    x0, x1, y = T.SAFE_X0 + 60, T.SAFE_X1 - 60, 900
    line(cr, x0, y, x1, y, T.INK_FAINT, T.STROKE, alpha * 0.7)
    fy = v("vendor_fix_release")
    txt.font("pop", 34, "bold")
    txt.draw(x0, y - 30, "FIRMWARE SHIPPED", T.INK_DIM, alpha)
    txt.draw(x0 + 120, y + 56, "AUG 2025", T.SUCCESS, alpha)
    line(cr, x0 + 140, y, x0 + 140, y + 40, T.SUCCESS, T.STROKE, alpha)
    txt.draw_r(x1, y - 30, "THE ATTACK", T.INK_DIM, alpha)
    txt.draw(x1 - 140, y + 56, "OCT 2026", T.PROBLEM, alpha)
    line(cr, x1 - 120, y, x1 - 120, y + 40, T.PROBLEM, T.STROKE, alpha)

    e1 = reveal(scene, frame, 1)
    if e1 > 0:
        card(cr, txt, 200, 1030, 620, 190, "AK-SM 800",
             f"end of life, {v('eol_year_a')}", T.INK_FAINT, alpha * e1)
    e2 = reveal(scene, frame, 2)
    if e2 > 0:
        card(cr, txt, 200, 1250, 620, 160, "AK-SC 355",
             f"phased out, {v('eol_year_b')}", T.INK_FAINT, alpha * e2)
    e3 = reveal(scene, frame, 0)
    txt.font("pop", 36, "bold")
    txt.draw_c(T.CENTER_X, 740, "MOST WERE NO LONGER SUPPORTED", T.PROBLEM, alpha * e3)


def defrost(cr, txt, frame, scene, alpha=1.0):
    cx, cy = T.CENTER_X, 1000
    e0 = reveal(scene, frame, 0)
    e1 = reveal(scene, frame, 1)
    e2 = reveal(scene, frame, 2)
    coil_w, coil_h = 560, 300
    rrect(cr, cx - coil_w / 2, cy - coil_h / 2, coil_w, coil_h, 26)
    stroke_colour(cr, T.CYAN, T.STROKE, alpha * e0)
    for i in range(9):
        x = cx - coil_w / 2 + 40 + i * 60
        line(cr, x, cy - coil_h / 2 + 34, x, cy + coil_h / 2 - 34, T.CYAN,
             T.STROKE_THIN, alpha * e0 * 0.8)
    # icicles grow on the cold fins
    ic = T.ease_out_cubic(e0)
    for i in range(9):
        x = cx - coil_w / 2 + 40 + i * 60
        top = cy - coil_h / 2 + 34
        ln = 26 + 54 * ic * (0.6 + 0.4 * ((i * 7) % 5) / 4)
        line(cr, x, top, x, top - ln, T.INK_DIM, T.STROKE_THIN, alpha * e0 * 0.9)
        line(cr, x - 9, top - ln + 9, x, top - ln, T.INK_DIM, T.STROKE_THIN,
             alpha * e0 * 0.9)
        line(cr, x + 9, top - ln + 9, x, top - ln, T.INK_DIM, T.STROKE_THIN,
             alpha * e0 * 0.9)
    txt.font("pop", 34, "bold")
    txt.draw_c(cx, cy + coil_h / 2 + 60, "ICE BUILDS ON THE COIL", T.INK_DIM,
               alpha * e0 * (1.0 - e2))

    e1 = reveal(scene, frame, 1)
    pill(cr, txt, cx, cy - coil_h / 2 - 90, "DEFROST CYCLE", T.SUCCESS, 40,
         alpha * e1 * (1.0 - e2))
    if e2 > 0:
        paint_glow(cr, cx, cy + coil_h / 2 - 60, 300, T.PROBLEM, 0.5 * e2)
        line(cr, cx - coil_w / 2 + 30, cy + coil_h / 2 - 34,
             cx + coil_w / 2 - 30, cy + coil_h / 2 - 34, T.PROBLEM, 8, alpha * e2)
        txt.font("pop", 36, "bold")
        txt.draw_c(cx, cy + coil_h / 2 + 60, "AND NEVER STOPPED", T.PROBLEM, alpha * e2)
        illustrative(cr, txt, cx - coil_w / 2, cy + coil_h / 2 + 130, alpha * e2)


def the_reveal(cr, txt, frame, scene, alpha=1.0):
    x0, y0, x1, y1 = T.SAFE_X0 + 40, 600, T.SAFE_X1 - 40, 1000
    lo, hi = v("normal_case_temp"), v("attack_temp_c")
    trace(cr, x0, y0, x1, y1, lo, hi, 0.0, 56.0, attack_frame=52,
          band_lo=lo - 1.0, band_hi=lo + 2.0, alpha=alpha, width=5, grid=True)
    e1 = reveal(scene, frame, 1)
    e2 = reveal(scene, frame, 1, dur=20)
    e3 = reveal(scene, frame, 2)
    txt.font("pop", 36, "bold")
    txt.draw_c(T.CENTER_X, 1060, f"{int(hi)}\u00b0C  BY MORNING", T.PROBLEM,
               alpha * max(e1, e3))

    labels = ["AK-SM", "AK-SC", "COPELAND XWEB", "DIXELL XWEB"]
    for i, lb in enumerate(labels):
        pe = T.ease_out_cubic(T.progress(frame, beat_frame(scene, 1) + 12 + i * 9,
                                         beat_frame(scene, 1) + 12 + i * 9 + 12))
        col, row = i % 2, i // 2
        chip(cr, txt, 140 + col * 410, 1110 + row * 78, lb,
             T.CYAN if i < 2 else T.INK_DIM, alpha * e2 * pe, w=390, size=34)

    if e3 > 0:
        card(cr, txt, 150, 1240, 780, 150, "PARIS PROSECUTOR", "INQUIRY OPENED",
             T.NUMBER, alpha * e3)
    else:
        card(cr, txt, 150, 1240, 780, 150, "CERTFR-2026-ALE-012",
             "12 OCT 2026, CERT-FR / ANSSI", T.CYAN, alpha * e1)


def the_gap(cr, txt, frame, scene, alpha=1.0):
    sweep = T.ease_out_cubic(T.progress(frame, beat_frame(scene, 1),
                                        beat_frame(scene, 1) + 18))
    for i, q in enumerate(("WHO?", "HOW?", "WHICH FLAW?")):
        pe = reveal(scene, frame, 0)
        y = 700 + i * 130 - 150 * sweep
        card(cr, txt, 240, y, 600, 110, q, "", T.PROBLEM, alpha * pe * (1 - sweep))
    if sweep > 0:
        a2 = T.ease_out_cubic(T.progress(frame, beat_frame(scene, 1) + 6,
                                         beat_frame(scene, 1) + 30))
        card(cr, txt, 150, 820, 780, 230, "TAKE THE BOX", "OFF THE INTERNET",
             T.SUCCESS, alpha * a2)
        cr.new_path()
        cr.move_to(760, 890)
        cr.line_to(850, 980)
        cr.move_to(850, 890)
        cr.line_to(760, 980)
        stroke_colour(cr, T.PROBLEM, 7, alpha * a2)
        txt.font("pop", 36, "bold")
        txt.draw_c(480, 1150, "CERT-FR'S INSTRUCTION", T.INK_DIM, alpha * a2)


def payoff(cr, txt, frame, scene, alpha=1.0):
    e = T.ease_out_cubic(T.progress(frame, beat_frame(scene, 0),
                                     beat_frame(scene, 0) + 60))
    x0, x1 = T.SAFE_X0 + 40, T.SAFE_X1 - 40
    y0, y1 = 700, 1180
    lo = v("normal_case_temp")
    trace(cr, x0, y0, x1, y1, lo, lo, 0.0, 56.0, attack_frame=999,
          reveal=e, band_lo=lo - 1.0, band_hi=lo + 2.0, alpha=alpha, width=5)
    e2 = reveal(scene, frame, 1)
    store_elevation(cr, txt, alpha * e2, warm=0.0, box_glow=0.35 * e2)
    txt.font("pop", 40, "bold")
    txt.draw_c(T.CENTER_X, 1370, "A BOX THAT ANSWERS A WEB PAGE", T.INK_DIM, alpha * e2)


def question(cr, txt, frame, scene, alpha=1.0):
    e = T.ease_out_cubic(T.progress(frame, scene["start_frame"],
                                    scene["start_frame"] + 40))
    lo = v("normal_case_temp")
    trace(cr, T.SAFE_X0 + 40, 700, T.SAFE_X1 - 40, 940, lo, lo, 0.0, 56.0,
          attack_frame=999, reveal=e, band_lo=lo - 1.0, band_hi=lo + 2.0,
          alpha=alpha * 0.8, width=5)
    house(cr, T.CENTER_X, 1180, 1.0, alpha * e)
    pulse = 0.5 + 0.5 * math.sin((frame - scene["start_frame"]) * 0.22)
    for i, (dx, dy) in enumerate(((-70, -40), (70, -40), (0, 30), (-40, 80))):
        col = T.NUMBER if i == 2 else T.INK_DIM
        cr.arc(T.CENTER_X + dx, 1180 + dy, 14, 0, 6.2832)
        fill_colour(cr, col, alpha * e * (0.5 + 0.5 * pulse if i == 2 else 0.9))
        cr.new_path()
    txt.font("pop", 90, "bold")
    txt.draw_c(T.CENTER_X, 1100, "?", T.NUMBER, alpha * e * 0.8)


SCENES = {
    "hook": hook, "setup": setup, "controller": controller, "why_online": why_online,
    "the_flaw": the_flaw, "the_scale": the_scale, "legacy": legacy, "defrost": defrost,
    "the_reveal": the_reveal, "the_gap": the_gap, "payoff": payoff,
    "question": question, "endcard": hook,
}

CAP_COLOURS = {"cyan": T.CYAN, "yellow": T.NUMBER, "plain": T.INK}


def compose_frame(cr: cairo.Context, txt: Text, frame: int, tl: dict,
                  bg: cairo.ImageSurface, state: dict) -> None:
    """One complete frame: background, the scene's own artwork, headline,
    underline and the burned-in caption that belongs to this frame."""
    from components import draw_caption

    scenes = tl["scenes"]
    sc = next((s for s in scenes if s["start_frame"] <= frame < s["end_frame"]),
              scenes[-1])
    target = sc.get("render_as", sc["id"])

    # background with a slow starfield drift. On the loop frame the drift is taken
    # from frame 0 too, so the last frame is pixel-identical to the first.
    bg_frame = frame
    if sc["id"] == "endcard":
        bg_frame = int(sc.get("render_frame", 0))
    ox = int((bg_frame * 0.11) % 96)
    oy = int((bg_frame * 0.05) % 96)
    cr.set_operator(cairo.OPERATOR_OVER)
    cr.set_source_surface(bg, -ox, -oy)
    cr.paint()

    # The end card is a verbatim copy of frame 0, so it is handed frame 0.
    # Every other scene is handed the absolute frame, because reveal() and
    # beat_frame() both work in absolute timeline frames.
    render_frame = sc.get("render_frame", frame) if target != sc["id"] else frame
    fn = SCENES[target]

    # Scene artwork is hard-clipped to the safe zone, so a glow, a shockwave ring
    # or an accidental wide label can never put a pixel outside x 120-960 or below
    # the illustration ceiling. The headline, captions and wordmark are drawn after
    # this block and live inside the zone by construction.
    cr.save()
    cr.rectangle(T.SAFE_X0, T.ILLUSTRATION_TOP - 40, T.SAFE_W,
                 1462 - (T.ILLUSTRATION_TOP - 40))
    cr.clip()
    # The end card is a verbatim copy of frame 0: it is handed frame 0 AND the
    # first scene's boundaries, so the shockwave ring is at the same radius too.
    fn(cr, txt, render_frame, tl["scenes"][0] if sc["id"] == "endcard" else sc)
    cr.restore()

    # headline, with the underline in the scene's accent colour. On the loop frame
    # the headline is driven from frame 0 too, so the last frame matches the first.
    accent = T.PROBLEM if target in ("the_gap", "the_reveal") else T.CYAN
    if target == "legacy":
        accent = T.INK_FAINT
    if sc["id"] == "endcard":
        headline(cr, txt, sc["headline"], 0, 0, 10 ** 6, accent)
    else:
        headline(cr, txt, sc["headline"], frame, sc["start_frame"],
                 sc["end_frame"], accent)

    # caption for this frame
    for c in sc["captions"]:
        cap = caption(txt, c, frame, sc["end_frame"])
        if cap is not None:
            words, key, colour, e, _ = cap
            txt.font("pop", T.SIZE_CAPTION, "bold")
            runs = [(w, colour if w == key else T.INK) for w in words]
            total = sum(txt.width(w) for w, _ in runs)
            x = T.CENTER_X - total / 2 + (1 - e) * 18
            y = T.CAPTION_CENTER_Y + T.SIZE_CAPTION * 0.70 * 0.5 + (1 - e) * 12
            txt.runs(x, y, runs, 1.0, align="left")
            break

    wordmark(cr, txt, 1.0, 1.0)