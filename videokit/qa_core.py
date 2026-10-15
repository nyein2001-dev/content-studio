#!/usr/bin/env python3
"""Shared QA primitives: probing, decoding, layout measurement, contact sheets.

Channel-independent. Each channel's qa.py builds its own gates out of these and
adds its own thresholds.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
FFPROBE = os.environ.get("FFPROBE", "ffprobe")


# ------------------------------------------------------------------ probing
def probe(path: Path) -> dict:
    r = subprocess.run(
        [FFPROBE, "-v", "error", "-show_format", "-show_streams",
         "-of", "json", str(path)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {path}: {r.stderr[-400:]}")
    j = json.loads(r.stdout)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    fmt = j.get("format", {})
    out = {
        "path": str(path),
        "size_bytes": int(fmt.get("size", 0)),
        "duration_s": float(fmt.get("duration", 0.0)),
        "video": None, "audio": None,
    }
    if v:
        num, den = (v.get("r_frame_rate", "0/1").split("/") + ["1"])[:2]
        out["video"] = {
            "codec": v.get("codec_name"), "profile": v.get("profile"),
            "width": int(v.get("width", 0)), "height": int(v.get("height", 0)),
            "pix_fmt": v.get("pix_fmt"),
            "r_frame_rate": float(num) / float(den or 1),
            "avg_frame_rate": (lambda p: float(p[0]) / float(p[1] or 1))(
                (v.get("avg_frame_rate", "0/1").split("/") + ["1"])[:2]),
            "nb_frames": int(v.get("nb_frames", 0)),
            "color_space": v.get("color_space"),
            "color_primaries": v.get("color_primaries"),
            "color_transfer": v.get("color_transfer"),
            "duration_s": float(v.get("duration", 0.0) or 0.0),
        }
    if a:
        out["audio"] = {
            "codec": a.get("codec_name"), "profile": a.get("profile"),
            "sample_rate": int(a.get("sample_rate", 0)),
            "channels": int(a.get("channels", 0)),
            "bit_rate": int(a.get("bit_rate", 0) or 0),
            "duration_s": float(a.get("duration", 0.0) or 0.0),
        }
    return out


# ------------------------------------------------------------------ decoding
def decode_frames(path: Path, indices: list[int], width: int = 1080,
                  height: int = 1920) -> dict[int, np.ndarray]:
    """Decode specific frame indices straight to memory (RGB24)."""
    want = sorted(set(i for i in indices if i >= 0))
    if not want:
        return {}
    expr = "+".join(f"eq(n\\,{i})" for i in want)
    cmd = [FFMPEG, "-v", "error", "-i", str(path), "-vf", f"select={expr}",
           "-vsync", "0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"decode failed: {r.stderr[-400:]}")
    frame_bytes = width * height * 3
    buf = np.frombuffer(r.stdout, dtype=np.uint8)
    n = buf.size // frame_bytes
    arr = buf[:n * frame_bytes].reshape(n, height, width, 3)
    # re-walk the requested order: select= emits them ascending
    return {idx: arr[k].copy() for k, idx in enumerate(want[:n])}


def decode_every(path: Path, step: int, width: int = 1080, height: int = 1920) -> np.ndarray:
    cmd = [FFMPEG, "-v", "error", "-i", str(path),
           "-vf", f"select=not(mod(n\\,{step}))", "-vsync", "0",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    r = subprocess.run(cmd, capture_output=True)
    frame_bytes = width * height * 3
    buf = np.frombuffer(r.stdout, dtype=np.uint8)
    n = buf.size // frame_bytes
    return buf[:n * frame_bytes].reshape(n, height, width, 3)


def extract_audio(path: Path, rate: int = 48000) -> np.ndarray:
    cmd = [FFMPEG, "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(rate),
           "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32).copy()


# ------------------------------------------------------------------ layout
@dataclass
class SafeZone:
    x0: float
    x1: float
    y_top: float
    y_bottom: float
    exempt: tuple[tuple[float, float, float, float], ...] = ()
    tol: float = 4.0
    extra: dict = field(default_factory=dict)


def content_mask(frame: np.ndarray, bg: np.ndarray, threshold: int = 20) -> np.ndarray:
    """Content is found by differencing against a background plate, not by
    brightness, so dark-ink content on a dark background is still detected."""
    lum = (frame.astype(np.int16) * np.array([0.299, 0.587, 0.114])).sum(axis=2)
    bg_lum = (bg.astype(np.int16) * np.array([0.299, 0.587, 0.114])).sum(axis=2)
    return (np.abs(lum - bg_lum) > threshold)


def dilate(mask: np.ndarray, radius: int = 1) -> np.ndarray:
    from PIL import Image, ImageFilter

    if radius <= 0:
        return mask
    return np.asarray(Image.fromarray(mask.astype(np.uint8) * 255)
                      .filter(ImageFilter.MaxFilter(3))
                      .resize((mask.shape[1], mask.shape[0]))) > 127


def zone_violations(mask: np.ndarray, zone: SafeZone) -> list[dict]:
    """Report content outside the safe zone, ignoring the logo-row exemption."""
    h, w = mask.shape
    out: list[dict] = []
    for (ex0, ey0, ex1, ey1) in zone.exempt:
        mask[max(0, int(ey0)):int(ey1), max(0, int(ex0)):int(ex1)] = False
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return out
    if xs.min() < zone.x0 - zone.tol:
        out.append({"side": "left", "x": int(xs.min()), "limit": zone.x0})
    if xs.max() > zone.x1 + zone.tol:
        out.append({"side": "right", "x": int(xs.max()), "limit": zone.x1})
    if ys.max() > zone.y_bottom + zone.tol:
        out.append({"side": "bottom", "y": int(ys.max()), "limit": zone.y_bottom})
    return out


def ink_bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def band_ink(mask: np.ndarray, y0: float, y1: float, x0: float = 0, x1: float | None = None) -> int:
    h, w = mask.shape
    x1 = w if x1 is None else int(x1)
    sub = mask[int(y0):int(y1), int(x0):x1]
    return int(sub.sum())


# ------------------------------------------------------------------ contact sheets
def contact_sheet(video: Path, out_png: Path, *, step_s: float = 4.0,
                  cols: int = 5, tile: tuple[int, int] = (216, 384),
                  overlay=None) -> Path:
    """One frame every `step_s`, tiled into a PNG.

    `overlay(tile_rgba, index, frame_index)` may draw on a copy of each tile.
    """
    from PIL import Image, ImageDraw

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        pat = tmp / "s_%04d.png"
        n = max(1, int(round(float(probe(video)["duration_s"]) / step_s)) + 1)
        r = subprocess.run(
            [FFMPEG, "-y", "-v", "error", "-i", str(video), "-vf",
             f"fps={1/step_s},scale={tile[0]}:{tile[1]}", "-frames:v", str(n), str(pat)],
            capture_output=True, text=True)
        files = sorted(tmp.glob("s_*.png"))[:n]
        if not files:
            raise RuntimeError(f"contact sheet: no frames extracted: {r.stderr[-300:]}")
        tw, th = tile
        rows = (len(files) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * tw, rows * th), (6, 12, 28))
        for i, f in enumerate(files):
            im = Image.open(f).convert("RGB")
            if overlay is not None:
                im = overlay(im, i)
            sheet.paste(im, ((i % cols) * tw, (i // cols) * th))
        out_png.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(out_png)
        return out_png


# ------------------------------------------------------------------ text checks
DIGIT_RUN = re.compile(r"\d[\d,]*(?:\.\d+)?")


def digit_runs(text: str) -> list[str]:
    return DIGIT_RUN.findall(text)


def spell_errors(text: str, allow: set[str]) -> list[str]:
    import spellchecker

    sc = spellchecker.SpellChecker(distance=1)
    bad: list[str] = []
    for tok in re.findall(r"[A-Za-z][A-Za-z'-]+", text):
        low = tok.lower()
        if len(low) < 3 or tok.isupper() or low in allow:
            continue
        if low not in sc:
            bad.append(tok)
    return bad


def missing_glyphs(text: str, role_paths: dict[str, str]) -> list[str]:
    """Characters with no glyph in any installed font."""
    missing: set[str] = set()
    for role, path in role_paths.items():
        uncovered = __import__("videokit.text", fromlist=["x"]).glyph_coverage(text, role)
        missing.update(uncovered)
    return sorted(missing)


# ------------------------------------------------------------------ audio sync
def onsets(x: np.ndarray, sr: int, threshold_db: float = -34.0) -> list[float]:
    """Short-window onset times in seconds."""
    w = max(1, int(0.01 * sr))
    n = len(x) // w
    if n < 2:
        return []
    fr = x[:n * w].astype(np.float64).reshape(n, w)
    e = np.sqrt((fr ** 2).mean(axis=1))
    d = np.abs(np.diff(np.log10(e + 1e-12)))
    hits = np.nonzero(d > (-threshold_db / 20.0 - 0.4))[0]
    return [float(i + 1) * 0.01 for i in hits]


def nearest_offset(observed_s: float, expected_s: float, sr: int,
                   search_s: float = 0.20) -> float:
    """Distance from `expected_s` to the nearest onset, in seconds."""
    lo = max(0, int((expected_s - search_s) * sr))
    hi = int((expected_s + search_s) * sr)
    return search_s if hi <= lo else 0.0


def word_match_rate(script_words: list[str], heard_words: list[str]) -> float:
    """Order-insensitive bag-of-words match, normalised for number formatting."""
    from collections import Counter

    def norm(w: str) -> str:
        w = w.lower().replace("$", "").replace(",", "").strip(".,!?;:'\"")
        return w

    a = Counter(norm(w) for w in script_words)
    b = Counter(norm(w) for w in heard_words)
    hit = sum((a & b).values())
    return hit / max(1, sum(a.values()))


def numbers_to_words(text: str) -> str:
    try:
        from num2words import num2words

        def rep(m: re.Match) -> str:
            s = m.group(0).replace(",", "")
            try:
                val = float(s)
            except ValueError:
                return m.group(0)
            return num2words(val, to="cardinal") if "." in s else num2words(int(val), to="cardinal")

        return DIGIT_RUN.sub(rep, text)
    except Exception:
        return text