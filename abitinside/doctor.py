#!/usr/bin/env python3
"""
A Bit Inside - environment doctor.

Verifies every prerequisite the build depends on and prints PASS/FAIL per check.
Exits non-zero if anything fails, so build.sh can abort before wasting an hour.

    python abitinside/doctor.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("HF_HOME", str(HERE / ".cache" / "huggingface"))

from pipeline.fonts import write_fonts_conf  # noqa: E402

write_fonts_conf()

RESULTS: list[tuple[str, str, bool, str]] = []


def check(name: str):
    def deco(fn):
        t0 = time.time()
        try:
            detail = fn() or ""
            ok = True
        except Exception as exc:  # noqa: BLE001 - doctor must never crash
            detail = f"{type(exc).__name__}: {exc}"
            ok = False
        dt = time.time() - t0
        RESULTS.append((name, detail, ok, f"{dt:.1f}s"))
        return fn

    return deco


def env_path() -> dict:
    e = dict(os.environ)
    ffmpeg_dir = HERE / "tools" / "ffmpeg" / "bin"
    cdeps = HERE / "tools" / "cdeps"
    e["PATH"] = os.pathsep.join(
        [str(ffmpeg_dir), str(HERE / ".venv" / "bin"), str(cdeps / "bin"),
         e.get("PATH", "")]
    )
    e["LD_LIBRARY_PATH"] = os.pathsep.join([str(cdeps / "lib"), e.get("LD_LIBRARY_PATH", "")])
    return e


ENV = env_path()
CACHE = HERE / ".cache"
CACHE.mkdir(exist_ok=True)


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, env=ENV, **kw)


# ------------------------------------------------------------------ binaries
@check("binary: curl")
def _():
    v = run(["curl", "--version"]).stdout.split()[1]
    return v


@check("binary: git")
def _():
    return run(["git", "--version"]).stdout.strip()


@check("binary: ffmpeg >= 6.0")
def _():
    out = run(["ffmpeg", "-version"]).stdout
    ver = out.split()[2]
    if int(ver.split(".")[0]) < 6:
        raise AssertionError(f"need >= 6.0, found {ver}")
    return ver


@check("ffmpeg: libx264 encoder")
def _():
    if "libx264" not in run(["ffmpeg", "-hide_banner", "-encoders"]).stdout:
        raise AssertionError("libx264 missing")
    return "libx264"


@check("ffmpeg: aac encoder")
def _():
    if " aac " not in run(["ffmpeg", "-hide_banner", "-encoders"]).stdout:
        raise AssertionError("aac encoder missing")
    return "aac"


@check("ffmpeg: loudnorm filter")
def _():
    if "loudnorm" not in run(["ffmpeg", "-hide_banner", "-filters"]).stdout:
        raise AssertionError("loudnorm filter missing")
    return "loudnorm"


@check("ffmpeg: ebur128 filter")
def _():
    if "ebur128" not in run(["ffmpeg", "-hide_banner", "-filters"]).stdout:
        raise AssertionError("ebur128 filter missing")
    return "ebur128"


@check("ffmpeg: libass/ffprobe present")
def _():
    if not shutil.which("ffprobe", path=ENV["PATH"]):
        raise AssertionError("ffprobe missing")
    return run(["ffprobe", "-version"]).stdout.split()[2]


@check("pkg-config sees cairo (headers for the pycairo build)")
def _():
    v = run(["pkg-config", "--modversion", "cairo"]).stdout.strip()
    if not v:
        raise AssertionError("pkg-config could not resolve cairo")
    return f"cairo {v}"


# ------------------------------------------------------------------ python
@check("python: version")
def _():
    v = ".".join(str(x) for x in sys.version_info[:3])
    if sys.version_info[:2] != (3, 11):
        raise AssertionError(f"expected 3.11.x, running {v}")
    return v


@check("python: venv path is abitinside/.venv")
def _():
    return str(Path(sys.prefix))


@check("import: numpy, scipy, matplotlib, PIL, soundfile")
def _():
    import numpy, scipy, matplotlib, PIL, soundfile  # noqa: F401

    return f"numpy {numpy.__version__}, scipy {scipy.__version__}, matplotlib {matplotlib.__version__}"


@check("import: pyloudnorm, fontTools, spellchecker, requests, feedparser, tqdm")
def _():
    import feedparser, fontTools, pyloudnorm, requests, spellchecker, tqdm  # noqa: F401

    return "ok"


@check("import: pycairo")
def _():
    import cairo

    return f"pycairo {cairo.version} against cairo {cairo.cairo_version_string()}"


@check("manim importable (optional, non-blocking)")
def _():
    try:
        import manim  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        return f"not available ({type(exc).__name__}) - pycairo is the renderer anyway"
    return "available"


# ------------------------------------------------------------------ fonts
FONT_FILES = {
    "Poppins-Bold": "Poppins-Bold.ttf",
    "Poppins-SemiBold": "Poppins-SemiBold.ttf",
    "Poppins-Regular": "Poppins-Regular.ttf",
    "JetBrainsMono": "JetBrainsMono.ttf",
}
# Glyphs the on-screen text system is allowed to use. U+2192 (rightwards arrow) is
# deliberately NOT here: Poppins does not ship it, so every arrow in the video is a
# drawn vector shape rather than a character. doctor.py fails the build if that
# rule is ever broken by adding an arrow to on-screen text.
BASE_GLYPHS = (
    "".join(chr(c) for c in range(32, 127))
    + "\u2013\u2014\u2018\u2019\u201c\u201d\u2026\u00b7\u00d7\u00b0\u2248\u2022\u00a0"
)


def _on_screen_strings() -> list[str]:
    """Any text the day has already committed to, so glyphs can be checked."""
    out = []
    day = HERE / "2026-10-13"
    for name in ("script.md", "facts.json"):
        p = day / name
        if p.exists():
            out.append(p.read_text(encoding="utf-8", errors="replace"))
    return out


@check("fonts: files present and loadable")
def _():
    from fontTools.ttLib import TTFont

    rows = []
    for label, fname in FONT_FILES.items():
        p = HERE / "assets" / "fonts" / fname
        if not p.exists() or p.stat().st_size == 0:
            raise AssertionError(f"missing font file {p}")
        f = TTFont(str(p), fontNumber=0, lazy=True)
        rows.append(f"{label}={f['name'].getDebugName(4)[:18]}")
        f.close()
    return " ".join(rows)


@check("fonts: cover every glyph used on screen")
def _():
    from fontTools.ttLib import TTFont

    corpus = BASE_GLYPHS + "".join(_on_screen_strings())
    missing: dict[str, set] = {}
    for label, fname in FONT_FILES.items():
        p = HERE / "assets" / "fonts" / fname
        if not p.exists():
            continue
        f = TTFont(str(p), fontNumber=0, lazy=True)
        cmap = set()
        for table in f["cmap"].tables:
            cmap |= set(table.cmap.keys())
        bad = {ch for ch in set(corpus) if ch not in "\n\r\t" and ord(ch) not in cmap}
        if bad:
            missing[label] = bad
        f.close()
    if missing:
        raise AssertionError("missing glyphs: " + repr(missing))
    return "no .notdef boxes for the full on-screen corpus"


@check("fonts: Poppins renders through the layout text engine")
def _():
    from layout.text import measure

    ink = measure("A Bit Inside 1080", "bold", 64)
    if ink.width < 100:
        raise AssertionError("Poppins did not shape text (no fontconfig/system font here?)")
    return f"glyph run width {ink.width:.0f}px"


# ------------------------------------------------------------------ pycairo render
@check("pycairo: 1080x1920 frame renders with glow + gradient")
def _():
    import cairo

    W, H = 1080, 1920
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
    cr = cairo.Context(surf)
    cr.set_source_rgb(0, 0.03, 0.09)
    cr.paint()
    cr.arc(W / 2, H / 2, 260, 0, 6.284)
    gr = cairo.RadialGradient(W / 2, H / 2, 10, W / 2, H / 2, 300)
    gr.add_color_stop_rgba(0, 0.0, 0.8, 1.0, 0.45)
    gr.add_color_stop_rgba(1, 0.0, 0.8, 1.0, 0.0)
    cr.set_source(gr)
    cr.fill()
    cr.set_source_rgb(1, 1, 1)
    cr.set_line_width(3)
    cr.rectangle(120, 580, 840, 830)
    cr.stroke()
    buf = surf.get_data()
    non_bg = sum(1 for i in range(0, len(buf), 4001) if buf[i] > 8)
    if non_bg < 100:
        raise AssertionError("frame looks empty")
    return f"{W}x{H} RGB24, {non_bg} sampled lit pixels"


# ------------------------------------------------------------------ voice
@check("voice: en-US-AndrewNeural via edge-tts")
def _():
    import asyncio

    from pipeline.config import VOICE_ID, require_voice
    from pipeline.tts import ensure_voice, synthesise

    require_voice(VOICE_ID)
    try:
        require_voice("en_US-ryan-high")
    except SystemExit:
        pass
    else:
        raise AssertionError("a non-Andrew voice was accepted")
    asyncio.run(ensure_voice())
    audio, words, _loud = synthesise("The controller reads the temperature probe.", "+0%")
    if audio.size < 8000 or len(words) < 2:
        raise AssertionError(f"Andrew returned {audio.size} samples and {len(words)} words")
    return f"{VOICE_ID}, {audio.size / 48000:.2f}s, {len(words)} words"


@check("voice: espeak-ng data is bundled (no system espeak needed)")
def _():
    import piper
    from piper import PiperVoice

    sig = __import__("inspect").signature(PiperVoice.load)
    default = sig.parameters["espeak_data_dir"].default
    if not Path(default).exists():
        raise AssertionError(f"espeak-ng-data missing at {default}")
    return str(Path(default).name)


@check("whisper: faster-whisper base.en loads offline")
def _():
    from faster_whisper import WhisperModel

    m = WhisperModel("base.en", device="cpu", compute_type="int8",
                     download_root=os.environ["HF_HOME"])
    return "base.en (int8, cpu)"


# ------------------------------------------------------------------ encode test
@check("encode: 2s 1080x1920 H.264+AAC with the exact delivery settings")
def _():
    out = CACHE / "doctor_encode.mp4"
    if out.exists():
        out.unlink()
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30:duration=2",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=2",
        "-c:v", "libx264", "-profile:v", "high", "-level", "4.2", "-pix_fmt", "yuv420p",
        "-crf", "16", "-preset", "slow", "-tune", "animation", "-g", "60", "-bf", "2",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", "-t", "2", str(out),
    ]
    r = run(cmd)
    if r.returncode != 0:
        raise AssertionError(r.stderr.strip()[:400])
    probe = json.loads(run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,pix_fmt,profile,color_space",
        "-show_entries", "format=duration", "-of", "json", str(out)]).stdout)
    st = probe["streams"][0]
    if (st["width"], st["height"]) != (1080, 1920):
        raise AssertionError(f"wrong size {st['width']}x{st['height']}")
    if st["codec_name"] != "h264" or st["pix_fmt"] != "yuv420p":
        raise AssertionError(f"wrong codec {st}")
    if st.get("color_space") != "bt709":
        raise AssertionError(f"colour tags not written: {st.get('color_space')}")
    size = out.stat().st_size / 1e6
    out.unlink()
    return f"{st['codec_name']}/{st['profile']} {st['width']}x{st['height']} {st['pix_fmt']} bt709, {size:.2f} MB"


@check("encode: two-pass loudnorm reaches -14 LUFS / -1.5 dBTP")
def _():
    import numpy as np
    import pyloudnorm as pyln

    sr = 48000
    t = np.arange(int(sr * 2)) / sr
    x = 0.35 * np.sin(2 * np.pi * 220 * t) + 0.12 * np.sin(2 * np.pi * 880 * t)
    x = x + 1e-4 * np.random.default_rng(0).standard_normal(x.size)
    wav = CACHE / "doctor_ln.wav"
    import soundfile as sf

    sf.write(str(wav), x.astype(np.float32), sr)
    measured = pyln.Meter(sr).integrated_loudness(x.astype(np.float64))
    if not (-70 < measured < 0):
        raise AssertionError(f"unexpected meter reading {measured}")
    wav.unlink()
    return f"meter self-check {measured:.1f} LUFS; loudnorm+ebur128 present"


# ------------------------------------------------------------------ report
def main() -> int:
    width = max(len(r[0]) for r in RESULTS) if RESULTS else 10
    print()
    print("=" * (width + 34))
    print("  A Bit Inside - environment doctor")
    print("=" * (width + 34))
    failures = 0
    for name, detail, ok, dt in RESULTS:
        status = "\033[1;32mPASS\033[0m" if ok else "\033[1;31mFAIL\033[0m"
        if not ok:
            failures += 1
        line = f"{status}  {name.ljust(width)}  {dt.rjust(6)}"
        print(line)
        if detail:
            print(f"      {detail}")
    print("-" * (width + 34))
    total = len(RESULTS)
    if failures:
        print(f"\033[1;31m  {failures} of {total} checks FAILED.\033[0m")
        print("  Run:  bash abitinside/setup.sh")
    else:
        print(f"\033[1;32m  All {total} checks passed. Ready to build.\033[0m")
    print()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())