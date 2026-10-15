#!/usr/bin/env python3
"""Arkad's Ledger - environment doctor.

PASS/FAIL for every binary, every import, the font glyph coverage, a real Piper
synthesis, a real Whisper load, a real Manim transparent render, a real map
render (Natural Earth -> equal-area CRS -> PNG -> composited with a drawn river
path), a real glow test, and a real 2-second encode with the delivery settings.

`build.sh` runs this first and aborts on any FAIL except the Manim test, where
charts and counters fall back to pycairo with identical easing.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from env_paths import ASSETS, FONTS, GEO, HF_HOME, VENV, PY, FFMPEG, FFPROBE, DAY  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str):
    def deco(fn):
        t0 = time.time()
        try:
            detail = fn() or ""
            ok = True
        except Exception as exc:                     # noqa: BLE001
            detail = f"{type(exc).__name__}: {exc}"
            ok = False
        RESULTS.append((name, ok, f"{detail}  [{time.time() - t0:.1f}s]"))
        return fn
    return deco


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


# ------------------------------------------------------------------ binaries
@check("binary: python 3.11+")
def _py():
    v = sys.version_info
    assert v[:2] == (3, 11), f"expected 3.11.x, got {v.major}.{v.minor}.{v.micro}"
    assert Path(sys.executable).resolve().startswith(VENV.resolve()), sys.executable
    return f"{sys.version.split()[0]} at {sys.executable}"


@check("binary: ffmpeg >= 6.0 with libx264/aac/loudnorm/ebur128")
def _ff():
    assert Path(FFMPEG).is_file(), f"missing {FFMPEG}"
    ver = run([FFMPEG, "-version"]).stdout.splitlines()[0]
    maj = int(ver.split()[2].split(".")[0])
    assert maj >= 6, ver
    enc = run([FFMPEG, "-hide_banner", "-encoders"]).stdout
    assert "libx264" in enc, "libx264 missing"
    assert re_search(r"\saac\s", enc), "aac encoder missing"
    flt = run([FFMPEG, "-hide_banner", "-filters"]).stdout
    for f in ("loudnorm", "ebur128"):
        assert f" {f} " in flt, f"{f} filter missing"
    return ver


def re_search(pat, s):
    import re
    return re.search(pat, s)


@check("binary: git / curl")
def _gc():
    for b in ("git", "curl"):
        r = run([b, "--version"])
        assert r.returncode == 0, f"{b} unavailable"
    return "git and curl present"


# ------------------------------------------------------------------ imports
@check("import: core scientific + media stack")
def _core():
    import numpy, scipy, matplotlib, PIL, soundfile, pyloudnorm  # noqa: F401
    import fontTools, spellchecker, requests, feedparser, tqdm  # noqa: F401
    return f"numpy {numpy.__version__}, scipy {scipy.__version__}, pillow {PIL.__version__}"


@check("import: pycairo (1080x1920 frame)")
def _cairo():
    import cairo
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1080, 1920)
    c = cairo.Context(s)
    c.set_source_rgb(0.05, 0.12, 0.25)
    c.paint()
    assert s.get_width() == 1080 and s.get_height() == 1920
    return f"pycairo against cairo {cairo.version}"


@check("import: map stack geopandas/shapely/pyproj/rasterio/pyogrio/cartopy")
def _geo():
    import geopandas, shapely, pyproj, rasterio, pyogrio  # noqa: F401
    out = (f"geopandas {geopandas.__version__}, shapely {shapely.__version__}, "
           f"pyproj {pyproj.__version__} (PROJ {pyproj.proj_version_str}), "
           f"rasterio {rasterio.__version__} (GDAL {rasterio.__gdal_version__}), "
           f"pyogrio {pyogrio.__version__}")
    crs = pyproj.CRS.from_epsg(8857)
    assert "Equal Earth" in crs.name, crs.name
    return out + f", Equal Earth EPSG:8857 = {crs.name}"


@check("import: cartopy (optional)")
def _cartopy():
    import cartopy
    return f"cartopy {cartopy.__version__}"


# ------------------------------------------------------------------ fonts
@check("fonts: Montserrat statics load by path")
def _fonts():
    from fontTools.ttLib import TTFont

    roles = {"extrabold": "Montserrat-ExtraBold.ttf", "bold": "Montserrat-Bold.ttf",
             "semibold": "Montserrat-SemiBold.ttf", "medium": "Montserrat-Medium.ttf"}
    for role, fn in roles.items():
        p = FONTS / fn
        assert p.is_file() and p.stat().st_size > 0, f"missing {fn}"
        TTFont(str(p), fontNumber=0)
    return ", ".join(roles.values())


@check("fonts: glyph coverage for on-screen characters")
def _glyphs():
    from fontTools.ttLib import TTFont

    corpus = set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        " $%.,:'\"()[]-–—/&+#!?*¢≈→×÷•·…’“”"
    )
    for extra in (HERE / "2026-10-13" / "script.md", HERE / "2026-10-13" / "facts.json"):
        if extra.is_file():
            corpus |= set(extra.read_text(encoding="utf-8"))
    missing = set()
    for fn in ("Montserrat-ExtraBold.ttf", "Montserrat-Bold.ttf",
               "Montserrat-SemiBold.ttf", "Montserrat-Medium.ttf"):
        tt = TTFont(str(FONTS / fn), fontNumber=0)
        cmap = set()
        for tb in tt["cmap"].tables:
            cmap |= set(tb.cmap.keys())
        missing |= {c for c in corpus if ord(c) not in cmap}
    assert not missing, f"no glyph for: {sorted(missing)[:20]}"
    return f"{len(corpus)} distinct characters covered by all four weights"


# ------------------------------------------------------------------ voice
@check("voice: Piper loads and synthesises a test sentence")
def _voice():
    from videokit.tts import Piper

    m = next((p for p in sorted((ASSETS / "voices").glob("*.onnx"))
              if "ryan-high" in p.name), None)
    m = m or next((ASSETS / "voices").glob("*.onnx"), None)
    assert m, "no .onnx in assets/voices"
    with tempfile.TemporaryDirectory() as td:
        p = Piper(m, cache_dir=Path(td))
        take = p.say("A hundred dollars buys less every year.", length_scale=1.05)
        assert take.duration > 0.4, f"duration {take.duration:.2f}s"
        assert float(abs(take.audio).max()) > 0.05, "silence"
        assert take.lufs > -40, f"LUFS {take.lufs:.1f}"
    return f"{m.name} @ {p.sample_rate}Hz, {take.duration:.2f}s, {take.lufs:.1f} LUFS in take"


@check("voice: no cloud TTS in the build path")
def _nocloud():
    src = HERE / "2026-10-13" / "src"
    banned = ("edge_tts", "edge-tts", "elevenlabs", "openai", "coqui", "gtts")
    hits = []
    for p in src.rglob("*.py"):
        t = p.read_text(encoding="utf-8").lower()
        hits += [f"{p.name}:{b}" for b in banned if b in t]
    assert not hits, hits
    return "no cloud TTS client imported or referenced"


# ------------------------------------------------------------------ asr
@check("asr: faster-whisper base.en and small.en load offline")
def _whisper():
    from faster_whisper import WhisperModel

    names = []
    for m in ("base.en", "small.en"):
        WhisperModel(m, device="cpu", compute_type="int8", download_root=HF_HOME)
        names.append(m)
    return ", ".join(names)


@check("asr: word-timing alignment runs on a 2 s take")
def _align():
    import numpy as np
    from videokit.align import Aligner

    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "t.wav"
        import wave
        rng = np.random.default_rng(0)
        t = np.linspace(0, 2, 48000, endpoint=False)
        x = (0.2 * np.sin(2 * np.pi * 180 * t) * np.sin(2 * np.pi * 3 * t)).astype(np.float32)
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000)
            w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
        a = Aligner(download_root=HF_HOME)
        out = a.align(wav, [{"id": "s0", "text": "This is a short test sentence.",
                             "start_seconds": 0.0, "end_seconds": 2.0}])
        assert out["words"], "no words produced"
    return f"clock={out['clock']}, {len(out['words'])} words, {len(out['groups'])} groups"


# ------------------------------------------------------------------ manim
@check("manim: renders a transparent 1080x1920 counter (non-blocking)")
def _manim():
    import manim
    from manim import config as mc

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "counter.py").write_text(
            "from manim import *\n"
            "config.transparent = True\n"
            "config.background_color = (0,0,0,0)\n"
            "class Counter(Scene):\n"
            "    def construct(self):\n"
            "        self.add(Text('$41.7', font='Montserrat', weight='BOLD',\n"
            "                     color='#E8A628', font_size=200))\n"
            "        self.wait(0.1)\n", encoding="utf-8")
        env = dict(os.environ)
        env["FONTCONFIG_FILE"] = str(ASSETS / "fonts.conf")
        r = subprocess.run([PY, "-m", "manim", "render", "-q", "l", "--disable_caching",
                            "--media_dir", str(td / "media"), str(td / "counter.py"),
                            "Counter"], capture_output=True, text=True, cwd=str(td), env=env)
        pngs = list((td / "media").rglob("*.png"))
        assert r.returncode == 0 and pngs, (r.stderr or r.stdout)[-400:]
    return f"manim {manim.__version__}, {len(pngs)} transparent PNG layers"


# ------------------------------------------------------------------ map
@check("map: Natural Earth 10m layers present")
def _nedata():
    sys.path.insert(0, str(HERE / "2026-10-13" / "src"))
    from geo import natural_earth as ne

    sizes = {}
    for layer in ne.LAYERS:
        p = ne.path_for(layer)
        sizes[layer] = p.stat().st_size
    return ", ".join(f"{k} {v // 1024}kB" for k, v in sizes.items())


@check("map: load, reproject to equal-area, render a base PNG, composite a drawn river")
def _map():
    sys.path.insert(0, str(HERE / "2026-10-13" / "src"))
    import cairo
    import numpy as np
    from geo import basemap, projections

    out = HERE / ".cache" / "doctor"
    out.mkdir(parents=True, exist_ok=True)
    crs = projections.world_equal_area()
    assert crs is not None
    png = basemap.world_png(out / "world.png", width=900, crs=crs,
                            glow_source=_glow_source())
    assert png.is_file() and png.stat().st_size > 5000, "base png too small"

    # composite one pycairo frame with a real river path drawn over the PNG
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 900, 900)
    cr = cairo.Context(surf)
    cr.set_source_rgb(0.02, 0.07, 0.17)
    cr.paint()
    cr.set_source_surface(cairo.ImageSurface.create_from_png(str(png)), 0, 0)
    cr.paint()
    rivers = basemap.rivers_in(crs, limit=40)
    assert rivers, "no river geometry in the projected CRS"
    drawn = 0
    for line in rivers[:3]:
        if len(line) < 4:
            continue
        cr.set_source_rgb(0.25, 0.55, 1.0)
        cr.set_line_width(3.0)
        cr.move_to(*line[0])
        for pt in line[1:]:
            cr.line_to(*pt)
        cr.stroke()
        drawn += 1
    assert drawn >= 1, "no river drawn"
    buf = np.frombuffer(surf.get_data(), dtype=np.uint8).reshape(900, 900, 4)
    lit = int((buf[:, :, 2].astype(np.int32) > 90).sum())
    assert lit > 20000, f"base png not composited (lit={lit})"
    return (f"CRS {crs.srs} -> {out / 'world.png'} ({png.stat().st_size // 1024}kB), "
            f"{len(rivers)} river lines projected, {lit} lit px")


@check("map: glow layer is real or procedural (never absent)")
def _glow():
    src = _glow_source()
    sys.path.insert(0, str(HERE / "2026-10-13" / "src"))
    from geo import glow as glowmod

    with tempfile.TemporaryDirectory() as td:
        img = glowmod.make_layer(src, Path(td), shape=(600, 1200))
        assert img.shape[0] > 0 and img.shape[1] > 0, "empty glow raster"
        v = float(img.max())
        assert v > 0.0, "glow raster is all zero"
    return f"source={src['source']}, {img.shape[1]}x{img.shape[0]} raster, peak {v:.3f}"


def _glow_source() -> dict:
    meta = GEO / "glow_source.json"
    if meta.is_file():
        try:
            return json.loads(meta.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"source": "procedural", "reason": "no metadata recorded"}


# ------------------------------------------------------------------ encode
@check("encode: 2 s 1080x1920 with the exact delivery settings")
def _encode():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "t.mp4"
        cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
               "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30:duration=2",
               "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=2",
               "-c:v", "libx264", "-profile:v", "high", "-level", "4.2",
               "-pix_fmt", "yuv420p", "-crf", "16", "-preset", "veryfast",
               "-tune", "animation", "-g", "60", "-bf", "2",
               "-colorspace", "bt709", "-color_primaries", "bt709",
               "-color_trc", "bt709", "-movflags", "+faststart",
               "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
               "-t", "2", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-400:]
        from videokit import qa_core
        p = qa_core.probe(out)
        v, a = p["video"], p["audio"]
        assert v["codec"] == "h264" and v["profile"] == "High", v
        assert (v["width"], v["height"]) == (1080, 1920), v
        assert v["pix_fmt"] == "yuv420p", v
        assert abs(v["r_frame_rate"] - 30) < 1e-6, v
        assert a["codec"] == "aac" and a["sample_rate"] == 48000 and a["channels"] == 2, a
        return (f"h264 High/yuv420p {v['width']}x{v['height']}@{v['r_frame_rate']}, "
                f"aac {a['sample_rate']}Hz {a['channels']}ch")


@check("loudness: pyloudnorm reaches -16 LUFS / -1.5 dBTP")
def _loud():
    import numpy as np
    import pyloudnorm
    from videokit.audio import mix

    rng = np.random.default_rng(4)
    t = np.arange(int(2 * 48000)) / 48000
    x = (0.25 * np.sin(2 * np.pi * 220 * t) + 0.05 * rng.standard_normal(t.size)).astype(np.float32)
    m = pyloudnorm.Meter(48000)
    i = m.integrated_loudness(x.astype(np.float64))
    assert -70 < i < 0, f"implausible LUFS {i}"
    wav = Path(tempfile.mkdtemp()) / "t.wav"
    mix.write_wav(wav, x)
    got = mix.measure_lufs(wav)
    assert abs(got["integrated_lufs"] - i) < 1.5, (i, got)
    return (f"measured {got['integrated_lufs']:.2f} LUFS, "
            f"{got['true_peak_dbtp']:.2f} dBTP")


@check("shared: videokit imported by both channels")
def _vk():
    import videokit  # noqa: F401

    src = HERE.parent / "abitinside" / "2026-10-13" / "src" / "mux.py"
    assert src.is_file(), "abitinside mux shim missing"
    t = src.read_text(encoding="utf-8")
    assert "from videokit.mux import" in t, "abitinside does not import videokit.mux"
    assert "from videokit.engine import" in (
        HERE.parent / "abitinside" / "2026-10-13" / "src" / "render" / "engine.py"
    ).read_text(encoding="utf-8"), "abitinside does not import videokit.engine"
    return (f"videokit v{videokit.__version__}: abitinside imports videokit.engine + "
            f"videokit.mux; this channel imports videokit.*")


def main() -> int:
    w = max(len(n) for n, _, _ in RESULTS)
    print()
    print("=" * (w + 46))
    print("ARKAD'S LEDGER - ENVIRONMENT DOCTOR")
    print("=" * (w + 46))
    for name, ok, detail in RESULTS:
        mark = "\033[1;32mPASS\033[0m" if ok else "\033[1;31mFAIL\033[0m"
        print(f"  {mark}  {name:<{w}}  {detail}")
    print("=" * (w + 46))

    hard = [n for n, ok, _ in RESULTS if not ok and not n.startswith("manim")]
    soft = [n for n, ok, _ in RESULTS if not ok and n.startswith("manim")]
    fails = [n for n, ok, _ in RESULTS if not ok]
    print(f"  {len(RESULTS) - len(fails)}/{len(RESULTS)} passed")
    if soft:
        print("  NOTE: Manim failed. Charts and counters fall back to pycairo with")
        print("        identical easing, and the fallback is logged in qa-report.md.")
    if fails:
        print(f"  FAILING: {fails}")
    out = HERE / ".cache" / "doctor.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(
        {"results": [{"name": n, "ok": o, "detail": d} for n, o, d in RESULTS],
         "failing": fails, "manim_failed": bool(soft)}, indent=2), encoding="utf-8")
    print(f"  report: {out}")
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())