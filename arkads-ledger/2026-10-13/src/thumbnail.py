#!/usr/bin/env python3
"""Thumbnail: 1080x1920 master PNG plus an upload-ready JPG under 2 MB."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3]))

import cairo  # noqa: E402
import numpy as np  # noqa: E402

import theme as T  # noqa: E402
from videokit import engine as E  # noqa: E402
from videokit import text as vt  # noqa: E402
from videokit import motion as M  # noqa: E402

DAY = HERE.parent
OUT = DAY / "thumbnail"
FACTS = json.loads((DAY / "facts.json").read_text(encoding="utf-8"))
F = FACTS["facts"]
YEAR = FACTS["year"]

# Two lines, five words total. Line 1 ivory, line 2 gold: the key word.
HEAD_LINE_1 = "ONE DOLLAR,"
HEAD_LINE_2 = "TWO TRUTHS"
HEADLINE_WORDS = len(HEAD_LINE_1.split()) + len(HEAD_LINE_2.split())


def render() -> Path:
    T.install_fonts()
    OUT.mkdir(parents=True, exist_ok=True)
    surf, cr = E.new_surface(T.W, T.H)

    # deep navy vertical gradient with faint light rays
    g = cairo.LinearGradient(0, 0, 0, T.H)
    g.add_color_stop_rgba(0.00, *E.rgb(T.BG_TOP), 1.0)
    g.add_color_stop_rgba(0.52, *E.rgb(T.BG_TOP), 1.0)
    g.add_color_stop_rgba(1.00, *E.rgb(T.BG_BOTTOM), 1.0)
    cr.set_source(g)
    cr.paint()
    for i in range(-7, 8):
        cr.set_source_rgba(*E.rgb(T.RAY), 0.030)
        cr.move_to(T.CENTER_X, -T.H * 0.18)
        cr.line_to(T.CENTER_X + M.clamp(0.0, 0.0, 0.0) + i * 96.0 + 540.0, T.H)
        cr.close_path()
        cr.fill()

    # the story's map: a dotted globe with a gold ring and the 7.79x figure
    cy = 860
    R = 300
    import math
    E.paint_glow(cr, T.CENTER_X, cy, 520, T.GOLD, 0.30)
    cr.set_source_rgba(*E.rgb(T.BLUE), 0.35)
    cr.set_line_width(2.5)
    for lat in (-60, -30, 0, 30, 60):
        ry = R * math.cos(math.radians(lat))
        yy = cy - R * math.sin(math.radians(lat))
        rx = math.sqrt(max(0.0, R * R - (yy - cy) ** 2))
        cr.save()
        cr.arc(T.CENTER_X, cy, 1, 0, 0)
        cr.restore()
        cr.set_line_width(2.0)
        cr.save()
        cr.translate(T.CENTER_X, yy)
        cr.scale(1.0, 0.22)
        cr.arc(0, 0, R, 0, 6.2832)
        cr.restore()
        cr.stroke()
        del ry, rx
    for lon in range(0, 180, 30):
        cr.save()
        cr.translate(T.CENTER_X, cy)
        cr.scale(math.cos(math.radians(lon)), 1.0)
        cr.arc(0, 0, R, -1.5708, 1.5708)
        cr.restore()
        cr.stroke()
    cr.set_source_rgba(*E.rgb(T.IVORY), 0.42)
    cr.set_line_width(3)
    cr.arc(T.CENTER_X, cy, R, 0, 6.2832)
    cr.stroke()

    # the one big number
    big = f"{F['ratio_ratio']['value']:.1f}x"
    size = 190
    E.paint_glow(cr, T.CENTER_X, cy + 8, 360, T.GOLD, 0.55)
    vt.draw(cr, T.CENTER_X - vt.advance(big, "extrabold", size) / 2, cy - 66,
            big, "extrabold", size, T.rgb("gold"), 1.0)
    vt.draw(cr, T.CENTER_X - vt.advance("PRICE LEVEL RATIO", "bold", 26) / 2, cy + 52,
            "PRICE LEVEL RATIO", "bold", 26, T.rgb("ivory"), 0.85)

    # logo row, inside the safe zone
    x, y, r = T.LOGO_X, T.LOGO_Y + 14, T.LOGO_R
    E.paint_glow(cr, x, y, 90, T.GOLD, 0.45)
    cr.set_source_rgb(*E.rgb(T.GOLD))
    cr.arc(x, y, r, 0, 6.2832)
    cr.fill()
    cr.set_source_rgb(*E.rgb(T.BG_TOP))
    E.rrect(cr, x - 13, y - 13, 9, 26, 4.5)
    cr.fill()
    E.rrect(cr, x + 4, y - 20, 9, 40, 4.5)
    cr.fill()
    vt.draw(cr, x + r + 18, y - 20, " ".join(T.WORDMARK), "semibold",
            T.SIZE_LOGO_WORD, T.rgb("ivory"), 1.0)

    # two-line headline, centred, equal margins, with a navy outline
    hs = 92
    y1 = 1180
    y2 = y1 + hs * 1.12
    w1 = vt.advance(HEAD_LINE_1, "extrabold", hs)
    w2 = vt.advance(HEAD_LINE_2, "extrabold", hs)
    for text, y, colour in ((HEAD_LINE_1, y1, T.rgb("ivory")),
                            (HEAD_LINE_2, y2, T.rgb("gold"))):
        w = vt.advance(text, "extrabold", hs)
        for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, 2)):
            vt.draw(cr, T.CENTER_X - w / 2 + dx, y + dy, text, "extrabold", hs,
                    T.rgb("bg_top"), 1.0)
        vt.draw(cr, T.CENTER_X - w / 2, y, text, "extrabold", hs, colour, 1.0)

    surf.flush()
    png = OUT / "sample-thumb.png"
    surf.write_to_png(str(png))

    # upload-ready JPG, sRGB, under 2 MB
    from PIL import Image
    jpg = OUT / "sample-thumb.jpg"
    Image.open(png).convert("RGB").save(jpg, "JPEG", quality=92, optimize=True,
                                        progressive=True, subsampling=0)
    return png


def check() -> dict:
    png = OUT / "sample-thumb.png"
    jpg = OUT / "sample-thumb.jpg"
    from PIL import Image

    w1 = vt.advance(HEAD_LINE_1, "extrabold", 92)
    w2 = vt.advance(HEAD_LINE_2, "extrabold", 92)
    m1 = T.CENTER_X - w1 / 2 - T.SAFE_X0
    m2 = T.SAFE_X1 - (T.CENTER_X + w1 / 2)
    n1 = T.CENTER_X - w2 / 2 - T.SAFE_X0
    n2 = T.SAFE_X1 - (T.CENTER_X + w2 / 2)
    im = Image.open(jpg)
    small = im.resize((270, 480), Image.LANCZOS)
    lum = np.asarray(small.convert("L"), dtype=float)
    contrast = float(lum.max() - lum.min())
    return {
        "png_bytes": png.stat().st_size, "jpg_bytes": jpg.stat().st_size,
        "png_size": Image.open(png).size, "jpg_size": im.size,
        "jpg_under_2mb": jpg.stat().st_size < 2 * 1024 * 1024,
        "headline_words": HEADLINE_WORDS,
        "headline_ok": HEADLINE_WORDS <= 5,
        "margin_diff_line1_px": round(abs(m1 - m2), 2),
        "margin_diff_line2_px": round(abs(n1 - n2), 2),
        "downscaled_contrast": round(contrast, 1),
        "content_box": [T.SAFE_X0, T.SAFE_TOP, T.SAFE_X1, T.SAFE_BOTTOM],
    }


if __name__ == "__main__":
    p = render()
    print(f"thumbnail: {p}")
    import json as _j
    print(_j.dumps(check(), indent=2))
