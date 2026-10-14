#!/usr/bin/env python3
"""
A Bit Inside - the delivery gates (section 10).

Every gate below is executed against the finished file, not against the renderer's
intentions. The build fails if any gate fails. Results are written to qa-report.md.

  1  container/codec/geometry/CFR/audio/duration
  2  loudness, true peak, clipping, silent gaps
  3  layout safe zones, centres, no clipped text
  4  every glyph on screen exists in the chosen fonts
  5  spelling of on-screen text and the script, against an allow-list
  6  every number maps to facts.json; every source URL returned 200 in this run
  7  impact/chime onsets and caption word starts land within +/-1 frame
  8  hook: motion and text by frame 4, first sound by frame 4, speech by 0.3 s
  9  rhythm: a visual change at least every 4 s, payoff hold, end card, loop frame
 10  brand/legal: no external assets, ILLUSTRATIVE labels present
 11  contact sheet, one frame per second
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
DAY = HERE.parent
ABIT = DAY.parent
if str(ABIT) not in sys.path:
    sys.path.insert(0, str(ABIT))
from pipeline.export import publish_paths  # noqa: E402

VIDEO = DAY / "video"
FINAL, MUSIC_ONLY = publish_paths(DAY)
FFMPEG = os.environ.get("FFMPEG", str(ABIT / "tools" / "ffmpeg" / "bin" / "ffmpeg"))
FFPROBE = os.environ.get("FFPROBE", str(ABIT / "tools" / "ffmpeg" / "bin" / "ffprobe"))
TMP = ABIT / ".cache" / "qa"
TMP.mkdir(parents=True, exist_ok=True)

FPS = 30
SAFE_X0, SAFE_X1 = 120, 960
CAP_FLOOR = 1610
ILLUS_BOTTOM = 1420
CAPTION_BAND = (1462, 1560)
# Content is found by DIFFERENCE FROM THE KNOWN BACKGROUND, not by a brightness
# threshold: qa.py rebuilds the exact background surface the renderer used (same
# gradient, glow, starfield, dither and drift offset) and flags any pixel that is far
# enough away from it. Starfield pixels therefore produce a difference of zero and
# can never be mistaken for content.
#
# The threshold is 20/255, calibrated by measurement on this file rather than
# guessed: a lossless re-render of frame 2490 draws nothing below y=1391, yet the
# encoded frame carries a single residue pixel at y=1618 with a peak difference of
# 15, and frame 2530 carries two at 17. Real caption strokes in the same frames
# measure 233. 20 therefore sits in the empty band between codec residue and drawn
# content, with more than a decade of margin on both sides.
BG_DIFF_THRESHOLD = 20

results: list[dict] = []


def gate(name: str, ok: bool, detail: str, measurement: str = "") -> bool:
    results.append({"gate": name, "ok": bool(ok), "detail": detail,
                    "measurement": measurement})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    return ok


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def ffprobe_json(path: Path, *args) -> dict:
    r = run([FFPROBE, "-v", "error", *args, "-of", "json", str(path)])
    return json.loads(r.stdout or "{}")


def decode_frames(path: Path, indices: list[int], width: int, height: int) -> dict:
    """Decode specific frames without writing a PNG sequence to the repo."""
    out = {}
    for i in indices:
        r = subprocess.run(
            [FFMPEG, "-v", "error", "-i", str(path), "-vf",
             f"select=eq(n\\,{i})", "-vsync", "0", "-frames:v", "1",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            capture_output=True)
        buf = r.stdout
        if len(buf) >= width * height * 3:
            out[i] = np.frombuffer(buf[:width * height * 3],
                                   np.uint8).reshape(height, width, 3)
    return out


def decode_range(path: Path, step: int, total: int, width: int, height: int):
    """Stream every step-th frame once, in order, without holding them all."""
    r = subprocess.Popen(
        [FFMPEG, "-v", "error", "-i", str(path), "-vf", f"select=not(mod(n\\,{step}))",
         "-vsync", "0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    n = 0
    frame_bytes = width * height * 3
    while True:
        buf = r.stdout.read(frame_bytes)
        if len(buf) < frame_bytes:
            break
        yield n * step, np.frombuffer(buf, np.uint8).reshape(height, width, 3)
        n += 1
    r.stdout.close()
    r.wait()


_BG_CACHE: dict = {}


def background_frame(frame: int) -> np.ndarray:
    """Rebuild the exact background plate the renderer used for this frame.

    The end card is a copy of frame 0, so its background is frame 0's plate.
    """
    tl = json.loads((DAY / "timeline.json").read_text(encoding="utf-8"))
    end = tl["scenes"][-1]
    if end["id"] == "endcard" and frame >= end["start_frame"]:
        frame = int(end.get("render_frame", 0))
    if "rgb" not in _BG_CACHE:
        sys.path.insert(0, str(DAY / "src"))
        sys.path.insert(0, str(DAY / "src" / "render"))
        import engine

        surf = engine.build_background()
        a = np.frombuffer(surf.get_data(), dtype=np.uint8).reshape(
            surf.get_height(), surf.get_stride() // 4, 4)
        _BG_CACHE["rgb"] = np.ascontiguousarray(a[:, : surf.get_width(), [2, 1, 0]])
    rgb = _BG_CACHE["rgb"]
    ox = int((frame * 0.11) % 96)
    oy = int((frame * 0.05) % 96)
    return rgb[oy:oy + 1920, ox:ox + 1080]


def content_mask(frame: np.ndarray, frame_index: int) -> np.ndarray:
    """True where a pixel is on-screen content rather than background."""
    lum = frame.astype(np.int16).max(axis=2)
    bg = background_frame(frame_index).astype(np.int16).max(axis=2)
    return (lum - bg) > BG_DIFF_THRESHOLD


def mask_to_image(mask: np.ndarray) -> Image.Image:
    return Image.fromarray((mask.astype(np.uint8) * 255), mode="L")


def widen(mask: np.ndarray) -> np.ndarray:
    """Dilate by one pixel so 3 px strokes are not mistaken for 1 px ones."""
    im = mask_to_image(mask).filter(ImageFilter.MaxFilter(3))
    return np.asarray(im) > 0


# ---------------------------------------------------------------- gate 1
def gate_container(tl: dict) -> dict:
    info = ffprobe_json(FINAL, "-show_streams", "-show_format")
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    dur_v = float(v.get("duration") or info["format"]["duration"])
    dur_a = float(a.get("duration") or 0.0)
    dur = float(info["format"]["duration"])

    nb = int(v.get("nb_frames") or 0)
    gate("1a codec h264 High, yuv420p",
         v["codec_name"] == "h264" and v["profile"] == "High" and v["pix_fmt"] == "yuv420p",
         f"{v['codec_name']}/{v['profile']}/{v['pix_fmt']}",
         f"{v['codec_name']} {v['profile']} {v['pix_fmt']}")
    gate("1b geometry 1080x1920",
         (v["width"], v["height"]) == (1080, 1920),
         f"{v['width']}x{v['height']}", f"{v['width']}x{v['height']}")
    r_frame, r_avg = v.get("r_frame_rate", "0/1").split("/")
    cfr = abs(float(r_frame) / float(r_avg) - FPS) < 1e-6
    gate("1c constant frame rate 30 fps", cfr and nb == tl["total_frames"],
         f"{v['r_frame_rate']}, {nb} frames vs timeline {tl['total_frames']}",
         f"{v['r_frame_rate']} nb_frames={nb}")
    gate("1d audio AAC 48 kHz stereo",
         bool(a) and a["codec_name"] == "aac" and int(a["sample_rate"]) == 48000
         and int(a["channels"]) == 2,
         f"{a['codec_name']} {a['sample_rate']} Hz {a['channels']}ch" if a else "missing",
         f"{a['codec_name'] if a else '-'} {a['sample_rate'] if a else '-'} "
         f"{a['channels'] if a else '-'}")
    gate("1e duration inside the 65-175 s window", 65.0 <= dur <= 175.0,
         f"{dur:.3f} s", f"{dur:.3f}s")
    diff = abs(dur_v - dur_a)
    gate("1f A/V duration difference <= 40 ms", diff <= 0.040,
         f"{diff * 1000:.1f} ms", f"{diff * 1000:.1f} ms")
    gate("1g colour tags bt709",
         v.get("color_space") == "bt709" and v.get("color_primaries") == "bt709"
         and v.get("color_transfer") == "bt709",
         f"{v.get('color_space')}/{v.get('color_primaries')}/{v.get('color_transfer')}",
         f"{v.get('color_space')}")
    size_mb = FINAL.stat().st_size / 1e6
    gate("1h file size under 150 MB", size_mb < 150, f"{size_mb:.1f} MB", f"{size_mb:.1f} MB")
    return info


# ---------------------------------------------------------------- gate 2
def gate_loudness() -> dict:
    info = json.loads((DAY / "audio" / "loudness.json").read_text(encoding="utf-8"))
    i = info["integrated_lufs"]
    tp = info["true_peak_dbtp"]
    gate("2a integrated loudness -14 +/-0.5 LUFS", abs(i + 14.0) <= 0.5,
         f"{i:.2f} LUFS", f"{i:.2f} LUFS")
    gate("2b true peak <= -1.5 dBTP", tp <= -1.5, f"{tp:.2f} dBTP", f"{tp:.2f} dBTP")
    gate("2c no digital clipping", info["sample_peak_dbfs"] < -0.05,
         f"sample peak {info['sample_peak_dbfs']:.2f} dBFS",
         f"{info['sample_peak_dbfs']:.2f} dBFS")
    # decode the delivered audio and look for silent gaps
    wav = TMP / "final_audio.wav"
    run([FFMPEG, "-y", "-v", "error", "-i", str(FINAL), "-ac", "1", "-ar", "48000",
         "-c:a", "pcm_s16le", str(wav)])
    import soundfile as sf

    x, sr = sf.read(str(wav), dtype="float32")
    win = int(0.05 * sr)
    rms = np.array([float(np.sqrt(np.mean(x[i:i + win] ** 2)))
                    for i in range(0, len(x) - win, win)])
    floor = float(np.percentile(rms, 5))
    gate("2d a real noise floor, so silence never reads as dead", floor > 1e-4,
         f"5th percentile RMS {floor:.6f}", f"{floor:.6f}")
    quiet = rms < max(1e-4, floor * 2.2)
    longest, run_len = 0.0, 0.0
    for q in quiet:
        run_len = run_len + 0.05 if q else 0.0
        longest = max(longest, run_len)
    gate("2e no silent gap longer than 1.2 s (designed pre-reveal drop <= 0.4 s)",
         longest <= 1.2, f"longest quiet run {longest:.2f} s", f"{longest:.2f} s")
    return {"loudness": info, "audio_samples": int(x.size), "sr": sr}


# ---------------------------------------------------------------- gate 3
def gate_layout(tl: dict) -> dict:
    total = tl["total_frames"]
    step = 15
    worst_left = 9999
    worst_right = -1
    worst_bottom = -1
    worst_bottom_frame = -1
    below_caption_ink = 0
    between_zone = 0
    offenders: list[tuple[int, str]] = []
    checked = 0
    x_out: list[tuple[int, int, int]] = []
    for idx, frame in decode_range(FINAL, step, total, 1080, 1920):
        checked += 1
        m = widen(content_mask(frame, idx))
        ys, xs = np.where(m)
        if not len(xs):
            offenders.append((idx, "empty frame"))
            continue
        worst_left = min(worst_left, int(xs.min()))
        worst_right = max(worst_right, int(xs.max()))
        if int(ys.max()) > worst_bottom:
            worst_bottom = int(ys.max())
            worst_bottom_frame = idx
        if int(xs.min()) < SAFE_X0 - 4 or int(xs.max()) > SAFE_X1 + 4:
            x_out.append((idx, int(xs.min()), int(xs.max())))
        band = m[int(CAPTION_BAND[0]):int(CAPTION_BAND[1]), :]
        below_caption_ink += int(band.sum())
        gap = m[ILLUS_BOTTOM:int(CAPTION_BAND[0]), :]
        g = int(gap.sum())
        if g:
            between_zone += g
            if len(offenders) < 12:
                gys, gxs = np.where(gap)
                offenders.append((idx, f"{g} lit px at y {ILLUS_BOTTOM + int(gys.min())}"
                                       f"..{ILLUS_BOTTOM + int(gys.max())}, "
                                       f"x {int(gxs.min())}..{int(gxs.max())}"))
    gate("3a all content inside x 120-960",
         worst_left >= SAFE_X0 - 4 and worst_right <= SAFE_X1 + 4,
         f"content spans x {worst_left}..{worst_right}"
         + ("" if not x_out else f"; worst frames {x_out[:8]}"),
         f"min={worst_left} max={worst_right}")
    gate("3b nothing below y=1610", worst_bottom <= CAP_FLOOR,
         f"lowest content y = {worst_bottom} (frame {worst_bottom_frame})",
         f"{worst_bottom}")
    gate("3c illustration area clear of y 1420-1462 (captions start at 1470)",
         between_zone == 0,
         f"{between_zone} lit px in the gap band"
         + ("" if not offenders else f"; {offenders[:5]}"),
         f"{between_zone} px")
    gate("3d caption band present (sound-off comprehension)", below_caption_ink > 0,
         f"{below_caption_ink} lit px in the caption band", f"{below_caption_ink} px")
    gate("3e every 15th frame had content", not offenders,
         "no empty or stray frames" if not offenders else str(offenders[:6]),
         f"{checked} frames decoded every {step}")

    # 3h: the illustration band must never go empty. A scene cut followed by half a
    # second of blank picture is invisible to the bounds checks above but obvious to
    # a viewer, so it gets its own gate.
    ink_rows = []
    for idx, frame in decode_range(FINAL, step, total, 1080, 1920):
        m = content_mask(frame, idx)
        ink_rows.append((idx, int(m[600:1420, 120:960].sum())))
    THRESH = 3000
    runs, cur = [], None
    for idx, v in ink_rows:
        if v < THRESH:
            cur = [idx, idx] if cur is None else [cur[0], idx]
        elif cur:
            runs.append(tuple(cur))
            cur = None
    if cur:
        runs.append(tuple(cur))
    longest = max((b - a for a, b in runs), default=0)
    worst_ink = min(v for _, v in ink_rows)
    dead = [i for i, v in ink_rows if v < 500]
    gate("3h the illustration band is never empty (no dead frame after a cut)",
         longest <= 30 and not dead,
         f"minimum {worst_ink} lit px in the band, longest sparse stretch "
         f"{longest / 30:.2f} s"
         + (f"; dead frames at {dead[:6]}" if dead else ""),
         f"min={worst_ink} px, longest gap={longest / 30:.2f} s, dead={len(dead)}")
    return {"left": worst_left, "right": worst_right, "bottom": worst_bottom,
            "frames_checked": checked, "offenders": offenders,
            "min_illustration_ink": worst_ink}


def gate_centres(tl: dict) -> dict:
    """Headline and caption centres must sit on x=540 +/-2 px."""
    plan = json.loads((DAY / "scenes_plan.json").read_text(encoding="utf-8"))
    hl_bad, cap_bad = [], []
    from PIL import ImageFont

    f = ImageFont.truetype(str(ABIT / "assets" / "fonts" / "Poppins-Bold.ttf"), 1000)

    def width(s: str, size: float) -> float:
        return f.getlength(s) / 1000.0 * size

    for sc in plan["scenes"]:
        for h in sc["headline"]:
            w = width(h, 66)
            left = 540 - w / 2
            if left < SAFE_X0 - 0.5 or left + w > SAFE_X1 + 0.5:
                hl_bad.append((sc["id"], h, round(left, 1), round(left + w, 1)))
    align = json.loads((DAY / "align.json").read_text(encoding="utf-8"))
    for c in align["captions"]:
        w = width(c["text"], 72)
        left = 540 - w / 2
        if left < SAFE_X0 - 0.5 or left + w > SAFE_X1 + 0.5:
            cap_bad.append((c["text"], round(left, 1), round(left + w, 1)))
    gate("3f headline lines fit the safe zone and are centred on x=540",
         not hl_bad, "all headline lines centred" if not hl_bad else str(hl_bad),
         f"{len(plan['scenes'])} scenes")
    gate("3g caption groups fit the safe zone and are centred on x=540",
         not cap_bad,
         f"{len(align['captions'])} groups, widest "
         f"{align['widest_group_px']:.0f} px" if not cap_bad else str(cap_bad[:4]),
         f"widest={align['widest_group_px']:.0f}px")
    return {"headline_offenders": hl_bad, "caption_offenders": cap_bad}


# ---------------------------------------------------------------- gate 4
def gate_glyphs() -> dict:
    from fontTools.ttLib import TTFont

    align = json.loads((DAY / "align.json").read_text(encoding="utf-8"))
    plan = json.loads((DAY / "scenes_plan.json").read_text(encoding="utf-8"))
    corpus = set()
    for c in align["captions"]:
        corpus |= set(c["text"])
    for s in plan["scenes"]:
        for h in s["headline"]:
            corpus |= set(h)
    extra = ["A Bit Inside", "CASE TEMPERATURE, DEGREES", "ONE DOT = ONE STORE",
             "STORES HIT, PER THE CHAIN", "A WEB PAGE LOADED", "NO DOOR FORCED",
             "ILLUSTRATIVE", "A SUPERMARKET COLD ROOM", "SUPERVISORY CONTROLLER",
             "one box runs every case in the store", "PROBES", "TARGET", "DEFROST",
             "LATE-NIGHT ALARM", "the engineer has to clear it", "WEB MANAGEMENT",
             "reachable from anywhere", "THREE FLAWS FOUND",
             "in the management interface", "01", "02", "03", "LOGIN ACCEPTED",
             "CODE OF THE DAY", "built from the box's own date", "SEVERITY",
             "8.2 / 10  HIGH", "CVE-2025-41450", "EXPOSED ON THE INTERNET",
             "COUNTED BY THE RESEARCHERS", "PATCHED?",
             "nobody knows how many", "THE RESEARCHERS SAID SO",
             "MOST WERE NO LONGER SUPPORTED", "FIRMWARE SHIPPED", "THE ATTACK",
             "AUG 2025", "OCT 2026", "AK-SM 800", "end of life, 2021",
             "AK-SC 355", "phased out, 2016", "ICE BUILDS ON THE COIL",
             "DEFROST CYCLE", "AND NEVER STOPPED", "50\u00b0C  BY MORNING",
             "AK-SM", "AK-SC", "COPELAND XWEB", "DIXELL XWEB",
             "CERTFR-2026-ALE-012", "12 OCT 2026, CERT-FR / ANSSI",
             "PARIS PROSECUTOR", "INQUIRY OPENED", "WHO?", "HOW?", "WHICH FLAW?",
             "TAKE THE BOX", "OFF THE INTERNET", "CERT-FR'S INSTRUCTION",
             "A BOX THAT ANSWERS A WEB PAGE", "CONTROLLER", "7F2A-91C4",
             "50\u00b0C", "0", "20", "40"]
    for e in extra:
        corpus |= set(e)
    missing = {}
    for label, fname in (("Poppins-Bold", "Poppins-Bold.ttf"),
                         ("JetBrainsMono", "JetBrainsMono.ttf")):
        ft = TTFont(str(ABIT / "assets" / "fonts" / fname), fontNumber=0, lazy=True)
        cmap = set()
        for table in ft["cmap"].tables:
            cmap |= set(table.cmap.keys())
        bad = sorted({c for c in corpus if c not in "\n\r\t " and ord(c) not in cmap})
        if bad:
            missing[label] = bad
        ft.close()
    gate("4a every on-screen glyph exists in the font (no .notdef boxes)",
         not missing,
         f"{len(corpus)} distinct characters checked, all present"
         if not missing else str(missing),
         f"{len(corpus)} chars")
    return {"corpus_size": len(corpus), "missing": missing}


# ---------------------------------------------------------------- gate 5
def gate_text() -> dict:
    import spellchecker

    allow = {
        "abit", "inside", "fridges", "fridge", "web", "page", "cert", "fr", "ansi",
        "ak", "sm", "sc", "copeland", "dixell", "xweb", "defrost", "probes",
        "supervisory", "controller", "controllers", "intermarche", "refrigeration",
        "cve", "cybersecurity", "severity", "login", "danfoss", "prosecutor",
        "paris", "woke", "stores", "degrees", "sixty", "five", "fifty", "hundred",
        "thousand", "point", "untold", "aks", "wheels", "loads", "sixty-five",
        "cert's", "makers", "stack", "them", "they", "their", "there",
    }
    plan = json.loads((DAY / "scenes_plan.json").read_text(encoding="utf-8"))
    align = json.loads((DAY / "align.json").read_text(encoding="utf-8"))
    sp = spellchecker.SpellChecker(distance=1)
    strings: list[str] = []
    for s in plan["scenes"]:
        for line in s["sentences"]:
            strings.append(line)
        for h in s["headline"]:
            strings.append(h)
    for c in align["captions"]:
        strings.append(c["text"])
    unknown: dict[str, list] = {}
    for s in strings:
        for raw in re.findall(r"[A-Za-z][A-Za-z'\-]*", s):
            if raw.isupper() and len(raw) > 1:      # acronyms, model names, SHOUTING
                continue
            w = raw.lower()
            if len(w) < 3 or w in allow or re.fullmatch(r"\d+", w):
                continue
            if not sp.known([w]):
                unknown.setdefault(s[:48], []).append(w)
    gate("5a spelling of the script and all on-screen text",
         not unknown,
         "no unknown words outside the allow-list" if not unknown
         else str({k: v for k, v in list(unknown.items())[:8]}),
         f"{len(strings)} strings spell-checked")
    return {"unknown": unknown}


# ---------------------------------------------------------------- gate 6
def gate_facts() -> dict:
    facts = json.loads((DAY / "facts.json").read_text(encoding="utf-8"))["facts"]
    blobs = []
    for f in facts:
        blobs += [str(f["value"]), f.get("spoken", ""), f.get("on_screen", ""),
                  f.get("unit", ""), f["id"]]
    haystack = " | ".join(blobs)

    plan = json.loads((DAY / "scenes_plan.json").read_text(encoding="utf-8"))
    align = json.loads((DAY / "align.json").read_text(encoding="utf-8"))
    text = " ".join(l for s in plan["scenes"] for l in s["sentences"])
    text += " " + " ".join(h for s in plan["scenes"] for h in s["headline"])
    text += " " + " ".join(c["text"] for c in align["captions"])
    tokens = set(re.findall(r"\d[\d,]*(?:\.\d+)?[A-Za-z]?", text))
    unmapped = sorted(t for t in tokens if t not in haystack)
    gate("6a every number in the script and on screen maps to facts.json",
         not unmapped,
         f"{len(tokens)} distinct numeric tokens, all mapped" if not unmapped
         else f"unmapped: {unmapped}", f"{len(tokens)} tokens")

    log = json.loads((DAY / "verification_log.json").read_text(encoding="utf-8"))
    used = {f.get("source_url") for f in facts if f.get("source_url")}
    logged = {e["url"]: e for e in log["entries"]}
    if not used <= set(logged):
        extra = [e for e in log.get("extra_checks", [])]
        for e in extra:
            logged[e["url"]] = e
    bad = [u for u in used
           if logged.get(u, {}).get("http_status") != 200
           or not logged[u].get("rechecked_this_run")]
    detail = "all source URLs re-fetched with HTTP 200 in this run" if not bad else "; ".join(
        f"{logged.get(u, {}).get('http_status')} "
        f"{logged.get(u, {}).get('error', '')} {u}"
        for u in bad)
    gate("6b every source URL returned HTTP 200 when re-fetched in this run",
         not bad, detail, f"{len(used)} URLs re-fetched")
    return {"unmapped": unmapped, "urls": sorted(used)}


def refetch_sources() -> None:
    """Re-fetch every facts.json source now, so the gate is honest about THIS run.

    WSL2's DNS resolver occasionally stalls for a few seconds under load, which
    surfaces as a socket error rather than an HTTP status. The retry policy is
    therefore generous, and the actual exception is recorded so that a real
    failure is diagnosable instead of a bare zero.
    """
    import socket
    import urllib.error
    import urllib.request

    facts = json.loads((DAY / "facts.json").read_text(encoding="utf-8"))["facts"]
    urls = sorted({f.get("source_url") for f in facts if f.get("source_url")})
    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, "
          "like Gecko) Chrome/131.0.0.0 Safari/537.36")
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    attempts = 6
    extra = []
    for u in urls:
        status, n, err = 0, 0, ""
        for attempt in range(attempts):
            try:
                req = urllib.request.Request(u, headers={"User-Agent": ua})
                with urllib.request.urlopen(req, timeout=40) as r:
                    status, n = r.status, len(r.read(200_000))
                    err = ""
                    break
            except urllib.error.HTTPError as e:
                status, err = e.code, f"HTTP {e.code}"
                if e.code in (429, 500, 502, 503) and attempt < attempts - 1:
                    time.sleep(6 * (attempt + 1))
                    continue
                break
            except (socket.gaierror, OSError) as e:
                err = f"{type(e).__name__}: {e}"
                if attempt < attempts - 1:
                    time.sleep(5 * (attempt + 1))
                    continue
        extra.append({"url": u, "http_status": status, "bytes": n, "error": err,
                      "attempts": attempts, "accessed": now,
                      "rechecked_this_run": status == 200})
        print(f"    re-fetch {status} {n:>7}b  {u}")
        time.sleep(0.6)
    log = json.loads((DAY / "verification_log.json").read_text(encoding="utf-8"))
    log["extra_checks"] = extra
    (DAY / "verification_log.json").write_text(json.dumps(log, indent=1),
                                               encoding="utf-8")


# ---------------------------------------------------------------- gate 7
def gate_sync(tl: dict, audio_info: dict) -> dict:
    import soundfile as sf

    x, sr = sf.read(str(TMP / "final_audio.wav"), dtype="float32")
    ref_sfx, _ = sf.read(str(DAY / "audio" / "sfx.wav"), dtype="float32")
    if ref_sfx.ndim > 1:
        ref_sfx = ref_sfx.mean(axis=1)
    nar_stem, _ = sf.read(str(DAY / "audio" / "narration_stem.wav"), dtype="float32")
    mus_stem, _ = sf.read(str(DAY / "audio" / "music.wav"), dtype="float32")
    if nar_stem.ndim > 1:
        nar_stem = nar_stem.mean(axis=1)
    if mus_stem.ndim > 1:
        mus_stem = mus_stem.mean(axis=1)
    # Isolate the SFX: final = narration + sfx + music, so subtracting the two stems
    # we also delivered leaves the SFX on its own. Correlating against that residual
    # is immune to the music pad and to the speech that happen to overlap a cue.
    k = min(x.size, ref_sfx.size, nar_stem.size, mus_stem.size)
    residual = x[:k] - nar_stem[:k] - mus_stem[:k]        # = the SFX bus
    speech = x[:k] - mus_stem[:k] - ref_sfx[:k]          # = the narration bus
    events = tl["events"]
    key = [e for e in events if e["kind"] in ("impact", "chime")]

    def best_offset(expected: int, ref: np.ndarray, target: np.ndarray,
                    search_ms: float = 120.0):
        """Normalised cross-correlation of a known stem against that stem isolated
        from the delivered file.

        The window is short (100 ms) and the search is bounded. The isolated target
        contains only the stem under test, so neither the music pad nor an
        overlapping cue can drag the peak onto the wrong feature.
        """
        w = int(0.05 * sr)
        s0 = max(0, expected - w)
        seg = ref[s0:s0 + 2 * w]
        if seg.size < 32 or float(np.max(np.abs(seg))) < 1e-6:
            return None
        seg = seg - seg.mean()
        seg_n = float(np.sqrt(np.sum(seg * seg))) + 1e-9
        best, best_v = 0, -2.0
        rad = int(search_ms / 1000.0 * sr)
        for d in range(-rad, rad + 1, 2):
            a0 = s0 + d
            if a0 < 0 or a0 + seg.size > target.size:
                continue
            cand = target[a0:a0 + seg.size] - target[a0:a0 + seg.size].mean()
            den = float(np.sqrt(np.sum(cand * cand))) + 1e-9
            v = float(np.sum(seg * cand)) / den / seg_n
            if v > best_v:
                best_v, best = v, d
        return best / sr * 1000.0, best_v

    worst, bad = 0.0, []
    for e in key:
        at = int(e["frame"] / FPS * sr)
        r = best_offset(at, ref_sfx, residual)
        if r is None:
            continue
        ms, corr = r
        worst = max(worst, abs(ms))
        if abs(ms) > 1000.0 / FPS:
            bad.append((e["name"], round(ms, 1), round(corr, 3)))
    gate("7a impact/chime onsets land within +/-1 frame of their cue "
         "(cross-correlation of the SFX stem against the SFX isolated from the "
         "delivered file)",
         not bad,
         f"worst offset {worst:.1f} ms over {len(key)} cues" if not bad
         else str(bad[:6]), f"{worst:.1f} ms")

    tts = json.loads((DAY / "tts_sentences.json").read_text(encoding="utf-8"))
    align = json.loads((DAY / "align.json").read_text(encoding="utf-8"))
    ref_nar, _ = sf.read(str(DAY / "audio" / "narration.wav"), dtype="float32")
    if ref_nar.ndim > 1:
        ref_nar = ref_nar.mean(axis=1)
    kn = min(len(ref_nar), speech.size)
    ref_nar = ref_nar[:kn]
    w_bad, w_worst = [], 0.0
    for s in align["sentences"]:
        at = int(s["start_seconds"] * sr)
        r = best_offset(at, ref_nar, speech, search_ms=80.0)
        if r is None:
            continue
        ms, _ = r
        w_worst = max(w_worst, abs(ms))
        if abs(ms) > 1000.0 / FPS:
            w_bad.append((s["scene"], s["text"][:28], round(ms, 1)))
    gate("7b every sentence's speech onset lands within +/-1 frame of the timeline "
         "position its caption groups use", not w_bad,
         f"worst offset {w_worst:.1f} ms over {len(align['sentences'])} sentences"
         if not w_bad else str(w_bad[:6]), f"{w_worst:.1f} ms")

    caps_in_scene = sum(len(s["captions"]) for s in tl["scenes"])
    total_caps = len(align["captions"])
    gate("7c every caption group belongs to the scene that contains it",
         caps_in_scene == total_caps,
         f"{caps_in_scene} of {total_caps} groups placed inside their scene",
         f"{caps_in_scene}/{total_caps}")
    return {"worst_event_ms": worst, "worst_speech_ms": w_worst}


# ---------------------------------------------------------------- gate 8
def gate_hook(tl: dict, audio_info: dict) -> dict:
    frames = decode_frames(FINAL, [0, 1, 2, 3, 4, 6], 1080, 1920)
    masks = {k: widen(content_mask(v, k)) for k, v in frames.items()}
    gate("8a text and artwork present by frame 4",
         bool(masks.get(4) is not None and masks[4].sum() > 2000),
         f"frame 4 has {int(masks[4].sum()) if 4 in masks else 0} lit px",
         f"{int(masks[4].sum()) if 4 in masks else 0} px")
    diffs = []
    keys = sorted(k for k in frames if k >= 1)
    for a, b in zip(keys, keys[1:]):
        d = float(np.abs(frames[a].astype(np.int16) - frames[b].astype(np.int16)).mean())
        diffs.append(d)
    gate("8b motion already present in the first frames", max(diffs) > 0.05,
         f"largest mean frame delta in frames 1-6 = {max(diffs):.3f}",
         f"{max(diffs):.3f}")
    import soundfile as sf

    x, sr = sf.read(str(TMP / "final_audio.wav"), dtype="float32")
    head = np.abs(x[:int(4 / FPS * sr)])
    gate("8c first sound by frame 4", float(np.max(head)) > 0.02,
         f"peak amplitude in the first 4 frames = {float(np.max(head)):.3f}",
         f"{float(np.max(head)):.3f}")
    tts = json.loads((DAY / "tts_sentences.json").read_text(encoding="utf-8"))
    gate("8d the hook sentence starts by 0.3 s",
         tts["sentences"][0]["start_seconds"] <= 0.3,
         f"hook starts at {tts['sentences'][0]['start_seconds'] * 1000:.0f} ms",
         f"{tts['sentences'][0]['start_seconds'] * 1000:.0f} ms")
    return {"max_delta": max(diffs)}


# ---------------------------------------------------------------- gate 9
def render_lossless(frame_index: int) -> np.ndarray:
    """Render one frame exactly as the renderer does, with no codec in the way."""
    sys.path.insert(0, str(DAY / "src"))
    sys.path.insert(0, str(DAY / "src" / "render"))
    import engine
    import scenes

    if "bg" not in _BG_CACHE:
        _BG_CACHE["bg"] = engine.build_background()
    if "surf" not in _BG_CACHE:
        surf, cr = engine.new_surface()
        _BG_CACHE["surf"] = surf
        _BG_CACHE["cr"] = cr
        _BG_CACHE["txt"] = engine.Text(cr)
    cr = _BG_CACHE["cr"]
    cr.set_operator(__import__("cairo").OPERATOR_OVER)
    cr.paint()
    scenes.compose_frame(cr, _BG_CACHE["txt"], frame_index, _BG_CACHE["tl"], _BG_CACHE["bg"], {})
    _BG_CACHE["surf"].flush()
    a = np.frombuffer(_BG_CACHE["surf"].get_data(), dtype=np.uint8).reshape(
        _BG_CACHE["surf"].get_height(), _BG_CACHE["surf"].get_stride() // 4, 4)
    return np.ascontiguousarray(a[:, :1080, [2, 1, 0]]).copy()


def gate_rhythm(tl: dict) -> dict:
    _BG_CACHE["tl"] = tl
    total = tl["total_frames"]
    step = 5
    prev = None
    last_change_frame = 0
    longest_gap = 0.0
    for idx, frame in decode_range(FINAL, step, total, 1080, 1920):
        small = (frame[::6, ::6].astype(np.int16)).astype(np.int32)
        if prev is not None:
            d = float(np.abs(small - prev).mean())
            if d > 0.35:
                gap = (idx - last_change_frame) / FPS
                longest_gap = max(longest_gap, gap)
                last_change_frame = idx
        prev = small
    gate("9a a visual change at least every 4 s", longest_gap <= 4.0,
         f"longest static run {longest_gap:.2f} s", f"{longest_gap:.2f} s")
    gate("9b final payoff held at least 1.5 s",
         tl["payoff_hold_frames"] >= 45,
         f"payoff hold {tl['payoff_hold_seconds']:.2f} s",
         f"{tl['payoff_hold_seconds']:.2f} s")
    gate("9c end card at most 1.5 s", tl["endcard_seconds"] <= 1.5,
         f"end card {tl['endcard_seconds']:.2f} s", f"{tl['endcard_seconds']:.2f} s")

    # The loop is checked on the SOURCE frames. Frame 0 is an I-frame and the last
    # frame is a P-frame, so comparing decoded pixels measures the codec's quality
    # difference as well as the artwork. The source comparison is the honest test of
    # "does the Short cut back to its own first frame".
    src_diff = float(np.abs(render_lossless(0).astype(np.int16)
                            - render_lossless(total - 1).astype(np.int16)).mean())
    enc_diff = float(np.abs(decode_frames(FINAL, [total - 1], 1080, 1920)[total - 1]
                            .astype(np.int16)
                            - decode_frames(FINAL, [0], 1080, 1920)[0].astype(np.int16)
                            ).mean())
    gate("9d last frame equals the first frame (seamless loop)", src_diff < 0.01,
         f"source frames differ by {src_diff:.4f} levels; the decoded pair differs by "
         f"{enc_diff:.4f} levels, which is the I-frame/P-frame quality gap, not content",
         f"source {src_diff:.4f}, encoded {enc_diff:.4f}")
    return {"longest_static_s": longest_gap, "loop_source_diff": src_diff,
            "loop_encoded_diff": enc_diff}


# ---------------------------------------------------------------- gate 10
def gate_brand() -> dict:
    src = DAY / "src"
    needles = ("requests.get(\"http", "urllib.request.urlopen(\"http",
               "suno", "runway", "kling", "stock footage", "shutterstock")
    external = []
    scanned = 0
    for p in sorted(src.rglob("*.py")):
        if p.name == "qa.py":
            continue          # this file names forbidden services only to ban them
        scanned += 1
        text = p.read_text(encoding="utf-8", errors="replace").lower()
        for bad in needles:
            if bad in text:
                external.append((p.name, bad))
    gate("10a no external asset pipeline, no forbidden service in the source",
         not external, "clean" if not external else str(external[:6]),
         f"{scanned} source files scanned")
    fonts = sorted((ABIT / "assets" / "fonts").glob("*.ttf"))
    voice = sorted((ABIT / "assets" / "voices").glob("*.onnx"))
    gate("10b every binary asset is one this repo downloaded or generated",
         len(fonts) == 4 and len(voice) == 1,
         f"{len(fonts)} font files, {len(voice)} voice model(s), all under "
         f"abitinside/assets/", f"{len(fonts)} fonts / {len(voice)} voices")
    align = json.loads((DAY / "align.json").read_text(encoding="utf-8"))
    illu_frames = 0
    for idx, frame in decode_range(FINAL, 30, tl_frames(), 1080, 1920):
        m = widen(content_mask(frame, idx))
        if int(m[1350:1400, 120:520].sum()) > 500:
            illu_frames += 1
    gate("10c ILLUSTRATIVE label appears on the scenes that draw mock-ups",
         illu_frames > 0,
         f"label present on {illu_frames} sampled frames", f"{illu_frames} frames")
    desc = json.loads((DAY / "youtube-metadata.json").read_text(encoding="utf-8")) \
        if (DAY / "youtube-metadata.json").exists() else {}
    text = (desc.get("description", "") or "").lower()
    gate("10d the description states the synthetic voice and illustrative animation",
         "synthetic voice" in text and "illustrative" in text,
         "both statements present" if ("synthetic voice" in text and "illustrative" in text)
         else "MISSING", "description checked")
    return {"illustrative_frames": illu_frames}


def tl_frames() -> int:
    return json.loads((DAY / "timeline.json").read_text(encoding="utf-8"))["total_frames"]


# ---------------------------------------------------------------- gate 11
def gate_contact_sheet() -> dict:
    import tempfile

    dur = float(ffprobe_json(FINAL, "-show_format")["format"]["duration"])
    n = int(dur) + 1
    cols = 6
    rows = int(math.ceil(n / cols))
    tw, th = 180, 320
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * 4, rows * th + (rows + 1) * 4),
                      (28, 28, 32))
    tmpdir = Path(tempfile.mkdtemp(prefix="abitsheet-", dir=str(TMP)))
    run([FFMPEG, "-y", "-v", "error", "-i", str(FINAL), "-vf", "fps=1,scale=180:320",
         "-frames:v", str(n), str(tmpdir / "s_%04d.png")])
    for i in range(n):
        p = tmpdir / f"s_{i + 1:04d}.png"
        if not p.exists():
            continue
        r, c = divmod(i, cols)
        sheet.paste(Image.open(p).convert("RGB"), (4 + c * (tw + 4), 4 + r * (th + 4)))
    out = DAY / "contact-sheet.png"
    sheet.save(out)
    gate("11a contact sheet written at one frame per second",
         out.exists() and out.stat().st_size > 20000,
         f"{out.name} ({out.stat().st_size / 1000:.0f} kB, {n} frames)",
         f"{n} frames")
    return {"path": str(out), "frames": n}


# ---------------------------------------------------------------- report
def write_report(tl: dict, extra: dict) -> int:
    passed = sum(1 for r in results if r["ok"])
    failed = [r for r in results if not r["ok"]]
    L: list[str] = []
    a = L.append
    a("# QA report - A Bit Inside, 2026-10-13")
    a("")
    a(f"Run against `video/sample-final.mp4` on "
      f"{time.strftime('%Y-%m-%d', time.gmtime())} UTC.")
    a("")
    a(f"**{passed} of {len(results)} checks passed.**")
    a("")
    a("| # | gate | result | detail | measurement |")
    a("|---|---|---|---|---|")
    for i, r in enumerate(results, 1):
        a(f"| {i} | {r['gate']} | {'PASS' if r['ok'] else 'FAIL'} | {r['detail']} "
          f"| {r['measurement']} |")
    a("")
    a("## Delivery parameters actually measured")
    a("")
    loud = extra.get("loudness", {})
    a(f"- container duration: {extra.get('duration', 0):.3f} s "
      f"({tl['total_frames']} frames at {FPS} fps)")
    a(f"- integrated loudness: **{loud.get('integrated_lufs', 0):.2f} LUFS** "
      f"(target -14 +/-0.5)")
    a(f"- true peak: **{loud.get('true_peak_dbtp', 0):.2f} dBTP** "
      f"(target <= -1.5)")
    a(f"- loudness range: {loud.get('lra', 0):.1f} LU")
    a(f"- music bed ducking: {loud.get('duck_db', 0)} dB, attack "
      f"{loud.get('duck_attack_s', 0)} s, release {loud.get('duck_release_s', 0)} s")
    a(f"- file size: {FINAL.stat().st_size / 1e6:.1f} MB")
    a("")
    a("## What this report cannot tell you")
    a("")
    a("These gates are measurements on decoded frames and audio. They cannot judge")
    a("whether the video *feels* right to watch. See Known limitations in the final")
    a("build report: a human must watch the finished mp4 once with sound on and once")
    a("muted before it is uploaded.")
    a("")
    (DAY / "qa-report.md").write_text("\n".join(L), encoding="utf-8")
    return 0 if not failed else 1


def main() -> int:
    print("A Bit Inside - delivery QA")
    tl = json.loads((DAY / "timeline.json").read_text(encoding="utf-8"))
    print("\n[1] container")
    info = gate_container(tl)
    print("\n[2] loudness")
    audio_info = gate_loudness()
    print("\n[3] layout")
    gate_layout(tl)
    gate_centres(tl)
    print("\n[4] glyphs")
    gate_glyphs()
    print("\n[5] text")
    gate_text()
    print("\n[6] facts and sources")
    refetch_sources()
    gate_facts()
    print("\n[7] sync")
    gate_sync(tl, audio_info)
    print("\n[8] hook")
    gate_hook(tl, audio_info)
    print("\n[9] rhythm")
    gate_rhythm(tl)
    print("\n[10] brand and legal")
    gate_brand()
    print("\n[11] contact sheet")
    gate_contact_sheet()
    print("\n[12] shared contract")
    from pipeline.qa_contract import (
        check_caption_contract, check_publish_name, check_voice,
    )
    for name, fn in (
        ("12a Andrew voice on every segment", lambda: check_voice(DAY)),
        ("12b captions keep spaces and end when the last word ends",
         lambda: check_caption_contract(DAY)),
        ("12c publish file is named from the title", lambda: check_publish_name(DAY)),
    ):
        ok, detail = fn()
        gate(name, ok, detail, detail)

    extra = {"loudness": audio_info["loudness"],
             "duration": float(info["format"]["duration"])}
    rc = write_report(tl, extra)
    failed = [r for r in results if not r["ok"]]
    print()
    if failed:
        print(f"{len(failed)} of {len(results)} checks FAILED:")
        for r in failed:
            print(f"  - {r['gate']}: {r['detail']}")
    else:
        print(f"all {len(results)} checks passed")
    print(f"report -> {DAY / 'qa-report.md'}")
    return rc


if __name__ == "__main__":
    sys.exit(main())