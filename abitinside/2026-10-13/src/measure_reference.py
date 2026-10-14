#!/usr/bin/env python3
"""
Measure the reference video (face-id-dots.mp4) so src/theme.py can be locked to
real numbers instead of guesses.

  1. FFmpeg extracts every 1/30 s frame (up to --max seconds) at native 576x1024.
  2. We compute, per frame:
       - background gradient (corners + centre column, ignoring lit pixels)
       - per-row "ink" density -> text/illustration bands
       - per-band x extents -> where things are centred, how wide they are
  3. Contact sheets are written so the layout can be inspected by eye.

Everything printed is scaled by SCALE = 1080/576 so it lands directly on the
1080x1920 canvas. The reference is never upscaled into the render; only its
measurements are scaled.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent        # .../abitinside/2026-10-13/src
DAY = HERE.parent                             # .../abitinside/2026-10-13
ABIT = DAY.parent                             # .../abitinside
REPO = ABIT.parent                            # content-studio (holds face-id-dots.mp4)
REF = REPO / "face-id-dots.mp4"
OUT = ABIT / ".cache" / "reference"

SCALE = 1080.0 / 576.0  # 1.875


def ffprobe_stream(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def extract(fps: int, frames: int) -> list[Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    for p in OUT.glob("f_*.png"):
        p.unlink()
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(REF),
         "-vf", f"fps={fps}", "-frames:v", str(frames), str(OUT / "f_%04d.png")],
        check=True)
    return sorted(OUT.glob("f_*.png"))


def hexof(rgb) -> str:
    return "#%02X%02X%02X" % tuple(int(round(c)) for c in rgb)


def analyse(paths: list[Path]) -> dict:
    W = H = None
    bands_per_frame = []
    bg_samples = []
    for p in paths:
        im = Image.open(p).convert("RGB")
        a = np.asarray(im).astype(np.int16)
        H, W = a.shape[:2]
        # "ink" = pixel that differs from the row's own dark background estimate.
        # Background here is a smooth dark gradient, so the 15th percentile of each
        # row is a good proxy for that row's background level.
        row_bg = np.percentile(a, 12, axis=1, keepdims=True)
        ink = (np.abs(a - row_bg).max(axis=2) > 26).sum(axis=1)  # lit pixels per row
        bands = []
        y = 0
        while y < H:
            if ink[y] > 2:
                y0 = y
                while y < H and ink[y] > 2:
                    y += 1
                y1 = y
                if y1 - y0 >= 3:
                    sub = ink[y0:y1]
                    cols = np.where((np.abs(a[y0:y1] - row_bg[y0:y1]).max(axis=2) > 26).any(axis=0))[0]
                    bands.append({
                        "y0": y0, "y1": y1, "h": y1 - y0,
                        "x0": int(cols.min()), "x1": int(cols.max()),
                        "cx": round(float((cols.min() + cols.max()) / 2), 1),
                        "peak_ink": int(sub.max()),
                        "density": round(float(sub.mean()), 1),
                    })
            y += 1
        bands_per_frame.append(bands)
        # background gradient: darkest corner, and the value 120px above the centre
        bg_samples.append({
            "tl": a[6, 6].tolist(), "tr": a[6, W - 7].tolist(),
            "bl": a[H - 7, 6].tolist(), "br": a[H - 7, W - 7].tolist(),
            "topmid": a[40, W // 2].tolist(), "botmid": a[H - 40, W // 2].tolist(),
        })
    bg = {k: hexof(np.median([s[k] for s in bg_samples], axis=0)) for k in bg_samples[0]}
    return {"W": W, "H": H, "frames": len(paths), "bg": bg, "bands": bands_per_frame}


def summarise(res: dict) -> None:
    W, H = res["W"], res["H"]
    print(f"\nreference {W}x{H}, {res['frames']} frames sampled at 1 fps")
    print("background (median of all sampled frames):")
    for k, v in res["bg"].items():
        print(f"   {k:8s} {v}")
    print(f"\nbands, scaled x{SCALE:.3f} to the 1080x1920 canvas")
    # Collect every band across all frames, normalised to a y-centre bucket.
    hist: dict[int, int] = {}
    widths: dict[int, list] = {}
    for bands in res["bands"]:
        for b in bands:
            k = int(round(((b["y0"] + b["y1"]) / 2) * SCALE / 10.0) * 10)
            hist[k] = hist.get(k, 0) + 1
            widths.setdefault(k, []).append((b["y1"] - b["y0"]) * SCALE)
    print(f"{'y centre':>9} {'frames':>7} {'h (1080px space)':>18}")
    for k in sorted(hist):
        if hist[k] < len(res["bands"]) * 0.25:
            continue
        hs = sorted(widths[k])
        print(f"{k:>9} {hist[k]:>7} {hs[0]:>8.0f}..{hs[-1]:<8.0f}")


def accent_colours(paths: list[Path]) -> list[tuple[str, int]]:
    """Cluster the saturated pixels across all frames into accent colours."""
    import colorsys

    buckets: dict[int, list] = {}
    for p in paths:
        a = np.asarray(Image.open(p).convert("RGB")).reshape(-1, 3).astype(np.float32) / 255.0
        mx = a.max(axis=1)
        mn = a.min(axis=1)
        sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
        v = mx
        sel = (sat > 0.45) & (v > 0.45)          # bright, clearly coloured pixels
        a = a[sel]
        if a.size == 0:
            continue
        # quantise to a coarse grid so anti-aliased edges collapse into the core colour
        q = (a * 12).astype(int)
        for row in q:
            buckets.setdefault(hash(tuple(row)), []).append(row / 12.0)
    merged = []
    for _, rows in buckets.items():
        merged.extend(rows)
    if not merged:
        return []
    arr = np.array(merged)
    out = []
    # simple 1-D histogram over hue, then average each occupied slice
    hues = np.array([colorsys.rgb_to_hsv(*r)[0] for r in arr])
    edges = np.linspace(0, 1, 25)
    for i in range(len(edges) - 1):
        m = (hues >= edges[i]) & (hues < edges[i + 1])
        if m.sum() < 200:
            continue
        med = np.median(arr[m], axis=0)
        out.append((hexof(med * 255), int(m.sum())))
    out.sort(key=lambda t: -t[1])
    return out


def full_res_frames(paths: list[Path], picks: list[int]) -> list[Path]:
    out = []
    for i in picks:
        if 0 <= i < len(paths):
            name = OUT / f"full_{i:04d}.png"
            shutil.copy(paths[i], name)
            out.append(name)
    return out


def sheets(paths: list[Path], cols: int = 6, rows: int = 5, tag: str = "") -> list[Path]:
    per = cols * rows
    out = []
    for si in range(0, len(paths), per):
        chunk = paths[si:si + per]
        first = Image.open(chunk[0])
        w, h = first.size
        sc = 0.34
        tw, th = int(w * sc), int(h * sc)
        pad = 6
        sheet = Image.new("RGB", (cols * tw + pad * (cols + 1), rows * th + pad * (rows + 1)),
                          (26, 26, 30))
        for i, p in enumerate(chunk):
            r, c = divmod(i, cols)
            t = Image.open(p).convert("RGB").resize((tw, th), Image.LANCZOS)
            sheet.paste(t, (pad + c * (tw + pad), pad + r * (th + pad)))
        name = OUT / f"sheet{tag}_{si // per:02d}.png"
        sheet.save(name)
        out.append(name)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fps", type=int, default=1)
    ap.add_argument("--max", type=int, default=60)
    args = ap.parse_args()
    if not REF.exists():
        print(f"reference not found: {REF}")
        return 1
    meta = ffprobe_stream(REF)
    v = next(s for s in meta["streams"] if s["codec_type"] == "video")
    a = next((s for s in meta["streams"] if s["codec_type"] == "audio"), None)
    print(f"reference video : {v['codec_name']} {v['width']}x{v['height']} "
          f"{v.get('r_frame_rate')} profile={v.get('profile')}")
    print(f"reference audio : {a['codec_name'] if a else 'none'} "
          f"{a['sample_rate'] if a else ''} {a['channels'] if a else ''} channels")
    print(f"duration        : {float(meta['format']['duration']):.3f}s")

    paths = extract(args.fps, args.max)
    res = analyse(paths)
    summarise(res)
    print("\naccent colours (bright, saturated pixels, median of each hue slice):")
    for hexv, n in accent_colours(paths)[:12]:
        print(f"   {hexv}  {n} px")

    names = sheets(paths)
    print("\ncontact sheets for visual inspection:")
    for n in names:
        print("  ", n)
    print("full-resolution frames:")
    for n in full_res_frames(paths, [2, 12, 30, 48]):
        print("  ", n)
    (OUT / "measure.json").write_text(json.dumps(
        {"bg": res["bg"], "W": res["W"], "H": res["H"], "scale": SCALE,
         "video": {k: v.get(k) for k in ("codec_name", "width", "height", "r_frame_rate",
                                         "profile", "pix_fmt", "level")}}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())