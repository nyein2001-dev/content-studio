#!/usr/bin/env python3
"""One function per scene, driven only by timeline.json and facts.json.

Every map scene draws a baked PNG through a camera. Per frame the loop only
composites and animates; geopandas never runs here.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3]))

import cairo  # noqa: E402

import theme as T  # noqa: E402
from videokit import engine as E  # noqa: E402
from videokit import motion as M  # noqa: E402
from videokit import text as vt  # noqa: E402

from geo import CACHE as GEO_CACHE  # noqa: E402
from geo import basemap, camera, choropleth, routes  # noqa: E402

DAY = HERE.parent
FACTS = json.loads((DAY / "facts.json").read_text(encoding="utf-8"))
F = FACTS["facts"]
YEAR = FACTS["year"]


MAP_RATIOS = {k.split("_")[-1]: v["value"] for k, v in F.items()
              if k.startswith("price_level_ratio_")}
MAP_NAMES = {k.split("_")[-1]: v.get("country", k) for k, v in F.items()
             if k.startswith("price_level_ratio_")}

# camera zoom budget: never more than three levels in the whole video
# The brief allows at most THREE zoom levels in the whole video: one wide
# establishing view, one working view, one close focus. Scenes share these.
ZOOM_WIDE, ZOOM_MID, ZOOM_CLOSE = 1.0, 2.05, 3.25
ZOOM = {"hook": ZOOM_WIDE, "setup": ZOOM_WIDE, "mechanism": ZOOM_WIDE,
        "dev_high": ZOOM_MID, "dev_mid": ZOOM_MID, "reveal": ZOOM_CLOSE,
        "payoff": ZOOM_MID, "close": ZOOM_WIDE}

_STATE: dict = {}


# ------------------------------------------------------------------ setup
def prepare() -> dict:
    """Bake every base map once, before the frame loop starts."""
    from geo import glow as glowmod
    from geo import projections

    crs = projections.world_equal_area()
    glow = glowmod.resolve(GEO_CACHE)
    baked = GEO_CACHE / "world_base.png"
    if not baked.is_file():
        basemap.world_png(baked, width=T.W, height=T.H, crs=crs, glow_source=glow,
                          max_zoom=max(ZOOM.values()), city_min_pop=900_000)
    surf, meta = basemap.load_baked(baked)
    cam = camera.Camera(surf, meta, canvas=(T.W, T.H))
    cx = (meta["extent"][0] + meta["extent"][2]) / 2.0
    cy = (meta["extent"][1] + meta["extent"][3]) / 2.0
    return {"cam": cam, "meta": meta, "crs": crs.srs, "cx": cx, "cy": cy,
            "glow": glow, "bg": E.build_background(T.PALETTE, T.GEOM, seed=20261013)}


def view_for(scene_id: str, t: float) -> camera.View:
    z = ZOOM.get(scene_id, 1.0)
    zoom = 1.0 + (z - 1.0) * M.ease_out_cubic(M.clamp01(t / 0.32))
    return camera.View(_STATE["cx"], _STATE["cy"], zoom)


# ------------------------------------------------------------------ chrome
def brand(cr: cairo.Context) -> None:
    """Logo row: gold coin with two navy bars, plus the letter-spaced wordmark."""
    x, y, r = T.LOGO_X, T.LOGO_Y + T.SIZE_LOGO_WORD * 0.28, T.LOGO_R
    E.paint_glow(cr, x, y, 96, T.GOLD, 0.45)
    cr.set_source_rgb(*E.rgb(T.GOLD))
    cr.arc(x, y, r, 0, 6.2832)
    cr.fill()
    bw, gap = T.LOGO_BAR_W, 7.0
    cr.set_source_rgb(*E.rgb(T.BG_TOP))
    E.rrect(cr, x - bw - gap / 2, y - 13, bw, 26, bw / 2)
    cr.fill()
    E.rrect(cr, x + gap / 2, y - 20, bw, 40, bw / 2)
    cr.fill()
    word = " ".join(T.WORDMARK)
    vt.draw(cr, x + r + 20, y - T.SIZE_LOGO_WORD * 0.34, word, "semibold",
            T.SIZE_LOGO_WORD, T.rgb("ivory"), 0.96)
    vt.draw(cr, x + r + 22, T.SERIES_Y, f"{T.SERIES}  ·  EP. {T.EPISODE}",
            "bold", T.SIZE_SERIES, T.rgb("gold"), 0.92)


def section(cr: cairo.Context, label: str, sub: str, alpha: float = 1.0) -> None:
    E.paint_glow(cr, T.SAFE_X0 - 8, T.SECTION_Y + 8, 150, T.GOLD, 0.30)
    cr.set_source_rgb(*E.rgb(T.GOLD))
    E.rrect(cr, T.SAFE_X0 - 8, T.SECTION_Y - 2, 5, T.SIZE_SECTION + 4, 2.5)
    cr.fill()
    w = vt.advance(label, "bold", T.SIZE_SECTION)
    vt.draw(cr, T.SAFE_X0 + 10, T.SECTION_Y, label, "bold", T.SIZE_SECTION,
            T.rgb("gold"), alpha)
    if sub:
        vt.draw(cr, T.SAFE_X0 + 10, T.SUB_LABEL_Y, sub, "medium", T.SIZE_SUB,
                T.rgb("muted"), alpha * 0.95)


def fit_headline(lines: list[str], line: str) -> float:
    """The width this line occupies at the size `headline` will choose."""
    avail = (T.SAFE_X1 - T.SAFE_X0) - 24.0
    size = float(T.SIZE_HERO)
    while size > 40 and max(vt.advance(l, "extrabold", size) for l in lines) > avail:
        size -= 2.0
    return vt.advance(line, "extrabold", size)


def headline(cr: cairo.Context, lines: list[str], frame: int, start: int,
             gold_last: bool = False) -> None:
    """Two lines, auto-fitted so neither line can ever leave the safe zone."""
    avail = (T.SAFE_X1 - T.SAFE_X0) - 24.0
    size = float(T.SIZE_HERO)
    for line in lines:
        size = min(size, avail / max(1e-6, vt.advance(line, "extrabold", size)
                                     / max(size, 1e-6)))
    # shrink until the widest line actually fits
    while size > 40 and max(vt.advance(l, "extrabold", size) for l in lines) > avail:
        size -= 2.0
    y = T.STAGE_TOP + 20
    pitch = size * 1.10
    block = pitch * len(lines)
    y = T.STAGE_TOP + max(0.0, (T.STAGE_BOTTOM - T.STAGE_TOP - block) * 0.18)
    for i, line in enumerate(lines):
        p = M.ease_out_cubic(M.progress(frame, start + i * 4,
                                        start + T.HEADLINE_IN + i * 4))
        colour = T.rgb("gold") if (gold_last and i == len(lines) - 1) else T.rgb("ivory")
        if p <= 0.001:
            y += pitch
            continue
        E.paint_glow(cr, T.CENTER_X, y + size * 0.36,
                     max(140, size * 1.2),
                     T.GOLD if gold_last else T.BLUE, 0.22 * p)
        vy = y + (1 - p) * 26
        vt.draw(cr, T.CENTER_X - vt.advance(line, "extrabold", size) / 2, vy,
                line, "extrabold", size, colour, p)
        y += pitch


def source_tag(cr: cairo.Context, alpha: float = 1.0) -> None:
    txt = f"Source: World Bank, World Development Indicators, {YEAR}"
    w = vt.advance(txt, "medium", T.SIZE_SOURCE)
    x = T.SAFE_X0 + 14
    E.paint_glow(cr, x - 12, T.SOURCE_Y + 8, 110, T.GOLD, 0.18 * alpha)
    cr.set_source_rgba(*E.rgb(T.GOLD), 0.85 * alpha)
    E.rrect(cr, x - 12, T.SOURCE_Y - 2, 4, T.SIZE_SOURCE + 8, 2)
    cr.fill()
    vt.draw(cr, x, T.SOURCE_Y, txt, "medium", T.SIZE_SOURCE, T.rgb("ivory_dim"),
            0.92 * alpha)


def caption(cr: cairo.Context, group: dict, frame: int, alpha: float) -> None:
    """Word-timed caption in a rounded dark pill. The spoken word is gold."""
    if alpha <= 0.004:
        return
    words = group["words"]
    size = T.SIZE_CAPTION
    runs = []
    for w in words:
        t = w["start"] * T.FPS
        e = w["end"] * T.FPS
        if frame < t:
            runs.append((w["text"], 0.45))
        elif frame <= e + 0.5 * T.FPS:
            runs.append((w["text"], 1.0))
        else:
            runs.append((w["text"], 0.92))
    total = sum(vt.advance(txt, "bold", size) + size * 0.26 for txt, _ in runs)
    pad_x, pad_y = 30, 16
    x0 = T.CENTER_X - total / 2 - pad_x
    y0 = T.CAPTION_CENTER_Y - size * 0.52 - pad_y
    h = size * 1.06 + pad_y * 2
    w = total + pad_x * 2
    # shrink to the safe width rather than overflow
    if w > T.CAPTION_MAX_W:
        cr.save()
        k = T.CAPTION_MAX_W / w
        cr.translate(T.CENTER_X, T.CAPTION_CENTER_Y)
        cr.scale(k, 1.0)
        cr.translate(-T.CENTER_X, -T.CAPTION_CENTER_Y)
    E.rrect(cr, x0, y0, w, h, h / 2)
    cr.set_source_rgba(*E.rgb(T.CAPTION_BG), 0.90 * alpha)
    cr.fill()
    cr.set_source_rgba(*E.rgb(T.PILL_EDGE), 0.55 * alpha)
    cr.set_line_width(2)
    cr.stroke()
    x = T.CENTER_X - total / 2
    for txt, bright in runs:
        adv = vt.advance(txt, "bold", size) + size * 0.26
        colour = T.rgb("gold") if bright >= 0.99 else T.rgb("ivory")
        a = alpha * (1.0 if bright >= 0.92 else 0.45)
        if bright >= 0.99:
            E.paint_glow(cr, x + adv / 2, T.CAPTION_CENTER_Y - 6, 70, T.GOLD, 0.30 * alpha)
        vt.draw(cr, x, T.CAPTION_CENTER_Y - size * 0.52, txt, "bold", size, colour, a)
        x += adv
    if w > T.CAPTION_MAX_W:
        cr.restore()


def pill(cr, x, y, w, h, text, alpha=1.0, colour=None, size=T.SIZE_CHIP):
    E.rrect(cr, x, y, w, h, h / 2)
    cr.set_source_rgba(*E.rgb(T.PILL_BG), 0.92 * alpha)
    cr.fill()
    cr.set_source_rgba(*E.rgb(T.PILL_EDGE), 0.7 * alpha)
    cr.set_line_width(2)
    cr.stroke()
    tw = vt.advance(text, "bold", size)
    vt.draw(cr, x + (w - tw) / 2, y + (h - size * 0.74) / 2, text, "bold", size,
            E.rgb(colour or T.GOLD), alpha)


def legend(cr, alpha: float) -> None:
    x, y = T.SAFE_X0, T.STAGE_BOTTOM - 46
    w = 420
    n = 56
    for i in range(n):
        r, g, b = choropleth.ramp(i / (n - 1))
        cr.set_source_rgba(r, g, b, 0.95 * alpha)
        cr.rectangle(x + i * (w / n), y, w / n + 0.6, 18)
        cr.fill()
    vt.draw(cr, x, y + 28, f"PRICE LEVEL RATIO TO THE US · {YEAR}", "medium",
            T.SIZE_SUB, T.rgb("muted"), alpha)
    vt.draw(cr, x + w, y + 28, "0.13", "medium", T.SIZE_SUB, T.rgb("ivory_dim"), alpha)
    vt.draw(cr, x + w + 46, y + 28, "1.00", "medium", T.SIZE_SUB, T.rgb("ivory_dim"), alpha)
    vt.draw(cr, x + w + 76, y + 28, "Boundaries: Natural Earth", "medium",
            T.SIZE_SUB, T.rgb("muted"), alpha * 0.9)


# ------------------------------------------------------------------ scenes
def _map_scene(cr, tl, sc, frame, draw_extra=None):
    span = max(1, sc["end"] - sc["start"])
    t = M.progress(frame, sc["start"], sc["end"])
    v = view_for(sc["id"], t)
    cam = _STATE["cam"]

    # map plate fades in behind the chrome
    a = M.ease_out_cubic(M.progress(frame, sc["start"], sc["start"] + 12))

    # Everything inside this band: the map, the fills, the pins and the callouts.
    # The brand row is drawn outside the clip, as its own element.
    cr.save()
    cr.rectangle(T.SAFE_X0, T.SAFE_TOP,
                 T.SAFE_X1 - T.SAFE_X0, T.SAFE_BOTTOM - T.SAFE_TOP)
    cr.clip()
    if a > 0.004:
        cam.draw(cr, v, alpha=0.98 * a)
    filled, unmatched = choropleth.fill_choropleth(
        cr, cam, MAP_RATIOS, v,
        progress=M.ease_out_cubic(M.clamp01(M.progress(frame, sc["start"], sc["start"] + 40))),
        key="ADM0_A3")
    if draw_extra:
        draw_extra(cr, cam, v, t, frame)
    cr.restore()
    if sc["id"] in ("hook", "dev_high", "dev_mid", "reveal", "payoff", "close"):
        legend(cr, a * M.clamp01(M.progress(frame, sc["start"] + 10, sc["start"] + 26)))
    return filled, unmatched


def _pin(cr, cam, v, lon, lat, label, value, appear: float, size=T.SIZE_LABEL):
    """Pin drop with a bounce, then a callout card with a leader line."""
    if appear <= 0.004:
        return
    x, y = cam.lonlat_to_screen(lon, lat, v)
    if not (T.SAFE_X0 < x < T.SAFE_X1 and T.STAGE_TOP < y < T.STAGE_BOTTOM):
        return
    p = M.ease_out_back(appear, 1.9)
    E.paint_glow(cr, x, y, 120, T.GOLD, 0.5 * appear)
    cr.set_source_rgb(*E.rgb(T.GOLD))
    cr.arc(x, y, 11 * p, 0, 6.2832)
    cr.fill()
    cr.set_source_rgba(*E.rgb(T.IVORY), 0.9 * appear)
    cr.set_line_width(3)
    cr.arc(x, y, 18 * p, 0, 6.2832)
    cr.stroke()
    text = f"{label}  {value}"
    tw = vt.advance(text, "bold", size)
    cw, ch = tw + 36, size * 1.9
    bx = min(T.SAFE_X1 - cw, max(T.SAFE_X0, x + 26))
    by = max(T.STAGE_TOP, min(T.STAGE_BOTTOM - ch, y - ch - 22))
    a = M.clamp01((appear - 0.35) / 0.35)
    cr.set_source_rgba(*E.rgb(T.GOLD), 0.75 * a)
    cr.set_line_width(2.5)
    cr.move_to(x + 16, y - 6)
    cr.line_to(bx, by + ch)
    cr.stroke()
    E.rrect(cr, bx, by, cw, ch, 12)
    cr.set_source_rgba(*E.rgb(T.CARD_BG), 0.94 * a)
    cr.fill()
    cr.set_source_rgba(*E.rgb(T.GOLD), 0.55 * a)
    cr.set_line_width(2)
    cr.stroke()
    vt.draw(cr, bx + 18, by + ch / 2 - size * 0.37, text, "bold", size,
            T.rgb("ivory"), a)


def _bars(cr, cam, v, items, appear: float):
    """Gold-gradient bars for the country-by-country beats."""
    if appear <= 0.004:
        return
    n = len(items)
    top = T.STAGE_TOP + 210
    h_max = 520
    gap = 14
    total_h = n * 34 + (n - 1) * gap
    y = top + (h_max - total_h) / 2
    for i, (name, value) in enumerate(items):
        p = M.ease_out_cubic(M.clamp01((appear - i * 0.11) / 0.5))
        if p <= 0.004:
            y += 34 + gap
            continue
        w = max(4.0, (value - 0.10) / 0.92 * 560 * p)
        x = T.CENTER_X - 300
        g = cairo.LinearGradient(x, 0, x + w, 0)
        g.add_color_stop_rgba(0.0, *E.rgb(T.GOLD_DEEP), 0.95 * p)
        g.add_color_stop_rgba(1.0, *E.rgb(T.GOLD), 0.98 * p)
        E.rrect(cr, x, y, w, 34, 6)
        cr.set_source(g)
        cr.fill()
        vt.draw(cr, x + w + 14, y + 7, f"{name}", "medium", 26, T.rgb("ivory_dim"),
                0.95 * p)
        vt.draw(cr, T.SAFE_X0 - 6, y + 7, f"{value:.3f}", "bold", 26,
                T.rgb("gold"), p)
        y += 34 + gap


def scene(cr, tl, sc, frame) -> None:
    st = _STATE["st"]
    span = max(1, sc["end"] - sc["start"])
    local = frame - sc["start"]
    beats = sc.get("beats", [sc["start"]])
    nbeat = max(1, len(beats))
    beat_t = M.clamp01((local - beats[0] + sc["start"]) / span) if beats else 0.0

    # headline out before the scene ends
    out_a = 1.0 - M.clamp01(M.progress(frame, sc["end"] - T.HEADLINE_OUT, sc["end"]))

    if sc["id"] == "endcard":
        _endcard(cr, frame, tl)
        return

    if sc["kind"] == "diagram":
        _mechanism(cr, sc, frame, beat_t)
    elif sc["kind"] == "map_split":
        _split(cr, tl, sc, frame, beat_t)
    elif sc["kind"] == "map_focus":
        _reveal(cr, tl, sc, frame)
    elif sc["kind"] == "map_bars":
        _bars_scene(cr, tl, sc, frame, beat_t)
    else:
        _map_scene(cr, tl, sc, frame)

    # chrome last so it is never occluded
    brand(cr)
    section(cr, sc["section"], sc["sub"], 1.0)
    if out_a > 0.004:
        headline(cr, sc["headline"], frame, sc["start"] + 6,
                 gold_last=(sc["id"] == "reveal"))
    source_tag(cr, 1.0)


def _mechanism(cr, sc, frame, beat_t):
    p = M.ease_out_cubic(M.progress(frame, sc["start"], sc["start"] + 16))
    y = T.STAGE_TOP + 300
    # left: a banknote (trade quote)
    bw, bh = 360, 200
    x0 = T.CENTER_X - 380
    E.rrect(cr, x0, y - bh / 2, bw, bh, 18)
    cr.set_source_rgba(*E.rgb(T.CARD_BG), 0.95 * p)
    cr.fill()
    cr.set_source_rgba(*E.rgb(T.BLUE), 0.7 * p)
    cr.set_line_width(3)
    cr.stroke()
    vt.draw(cr, x0 + bw / 2 - vt.advance("EXCHANGE RATE", "bold", 26) / 2,
            y - 34, "EXCHANGE RATE", "bold", 26, T.rgb("blue"), p)
    vt.draw(cr, x0 + bw / 2 - vt.advance("a trade quote", "medium", 24) / 2,
            y + 6, "a trade quote", "medium", 24, T.rgb("muted"), p)
    # right: a basket (shopping list)
    x1 = T.CENTER_X + 20
    E.rrect(cr, x1, y - bh / 2, bw, bh, 18)
    cr.set_source_rgba(*E.rgb(T.CARD_BG), 0.95 * p)
    cr.fill()
    cr.set_source_rgba(*E.rgb(T.GOLD), 0.8 * p)
    cr.set_line_width(3)
    cr.stroke()
    vt.draw(cr, x1 + bw / 2 - vt.advance("PRICE LEVEL", "bold", 26) / 2,
            y - 34, "PRICE LEVEL", "bold", 26, T.rgb("gold"), p)
    vt.draw(cr, x1 + bw / 2 - vt.advance("a shopping list", "medium", 24) / 2,
            y + 6, "a shopping list", "medium", 24, T.rgb("muted"), p)
    # the gap between them
    gap_a = M.clamp01((beat_t - 0.25) / 0.4) * p
    if gap_a > 0.004:
        cr.set_source_rgba(*E.rgb(T.CORAL), 0.75 * gap_a)
        cr.set_line_width(4)
        cr.move_to(T.CENTER_X - 14, y)
        cr.line_to(T.CENTER_X + 6, y)
        cr.stroke()
        vt.draw(cr, T.CENTER_X - 150, y + 120, "THEY DRIFT APART", "bold", 24,
                T.rgb("coral"), gap_a)


def _split(cr, tl, sc, frame, beat_t):
    _map_scene(cr, tl, sc, frame, _split_extra)


def _split_extra(cr, cam, v, t, frame):
    f0 = _STATE["st"]["setup"]["start"]
    _pin(cr, cam, v, -74.0, 40.7, "UNITED STATES", "1.000",
         M.clamp01((frame - f0) / 26.0) * 0.8)
    _pin(cr, cam, v, 8.7, 9.1, "NIGERIA", "0.128",
         M.clamp01((frame - f0 - 18) / 26.0))


def _bars_scene(cr, tl, sc, frame, beat_t):
    items = _SCENE_BARS.get(sc["id"], [])
    appear = M.clamp01((frame - sc["start"]) / 30.0)
    _map_scene(cr, tl, sc, frame, None)
    if sc["id"] == "dev_high":
        _bars(cr, _STATE["cam"], view_for(sc["id"], beat_t), items, appear)
    else:
        _map_scene(cr, tl, sc, frame,
                   lambda c, cam, v, t, f: _pin(c, cam, v, -99.1, 19.4,
                                                "MEXICO", "0.537",
                                                M.clamp01((f - sc["start"] - 8) / 24.0)))
        _bars(cr, _STATE["cam"], view_for(sc["id"], beat_t), items, appear)


def _reveal(cr, tl, sc, frame):
    shake_x, shake_y = M.shake(frame, sc["beats"][1], sc["beats"][1] + 12, T.SHAKE_MAX_PX, 16)
    cr.save()
    cr.translate(shake_x, shake_y)
    appear = M.clamp01((frame - sc["beats"][0]) / 22.0)
    _map_scene(cr, tl, sc, frame,
               lambda c, cam, v, t, f: _pin(
                   c, cam, v, 8.7, 9.1, "NIGERIA", "0.128",
                   M.clamp01((f - sc["beats"][0]) / 20.0), size=40))
    cr.restore()


def _endcard(cr, frame, tl):
    ec = tl["endcard"]
    t = M.clamp01((frame - ec["start"]) / 18.0)
    a = M.ease_out_cubic(t)
    x = T.CENTER_X
    y = T.CENTER_Y if hasattr(T, "CENTER_Y") else 880
    E.paint_glow(cr, x, y, 420, T.GOLD, 0.42 * a)
    cr.set_source_rgba(*E.rgb(T.GOLD), a)
    cr.arc(x, y - 70, 64, 0, 6.2832)
    cr.fill()
    cr.set_source_rgb(*E.rgb(T.BG_TOP))
    E.rrect(cr, x - 13, y - 100, 11, 34, 5.5)
    cr.fill()
    E.rrect(cr, x + 2, y - 112, 11, 52, 5.5)
    cr.fill()
    word = " ".join(T.WORDMARK)
    w = vt.advance(word, "extrabold", 64)
    vt.draw(cr, x - w / 2, y + 20, word, "extrabold", 64, T.rgb("ivory"), a)
    sub = "MAP OF MONEY  ·  EP. 2"
    w2 = vt.advance(sub, "bold", 28)
    vt.draw(cr, x - w2 / 2, y + 100, sub, "bold", 28, T.rgb("gold"), a * 0.9)


_SCENE_BARS = {
    "dev_high": [("United States", 1.000), ("United Kingdom", 0.892),
                 ("Germany", 0.802), ("Japan", 0.649), ("South Korea", 0.574)],
    "dev_mid": [("Mexico", 0.537), ("China", 0.473), ("Brazil", 0.457),
                ("Türkiye", 0.411), ("Indonesia", 0.287)],
}


# ------------------------------------------------------------------ frame
def compose_frame(cr, frame: int, tl: dict) -> None:
    if not _STATE:
        _STATE.update(prepare())
        _STATE["st"] = {s["id"]: s for s in tl["scenes"]}
        _STATE["tl"] = tl
        T.install_fonts()

    sc = None
    for s in tl["scenes"]:
        if s["start"] <= frame < s["end"]:
            sc = s
            break
    if sc is None:
        if frame >= tl["endcard"]["start"]:
            _endcard(cr, frame, tl)
        else:
            brand(cr)
        return

    # background plate, drifting
    dx = -((frame * 0.11) % 96) - 48
    dy = -((frame * 0.05) % 96) - 48
    cr.set_source_surface(_STATE["bg"], dx, dy)
    cr.paint()

    scene(cr, tl, sc, frame)

    # caption on top of everything except the end card
    if sc["id"] != "close":
        g = _caption_at(tl, frame)
        if g:
            a = M.clamp01((frame - g["start_frame"]) / T.CAPTION_IN)
            caption(cr, g, frame, a)


def _caption_at(tl, frame) -> dict | None:
    for g in tl["captions"]:
        if g["start_frame"] <= frame < g["end_frame"]:
            return g
    return None
