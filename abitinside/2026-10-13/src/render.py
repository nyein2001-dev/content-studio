#!/usr/bin/env python3
"""
A Bit Inside - the render driver.

Renders every frame at 1080x1920 with pycairo across all available cores, pipes
raw RGB into FFmpeg's stdin (never a PNG sequence), and muxes the mastered audio
into the two deliverables:

    video/sample-final.mp4            narration + SFX + music
    video/sample-music-sfx-only.mp4   SFX + music, no narration
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DAY = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "render"))

import theme as T  # noqa: E402
from engine import install_fonts, render_to_ffmpeg  # noqa: E402
from mux import deliver  # noqa: E402

VIDEO = DAY / "video"


def main() -> int:
    VIDEO.mkdir(exist_ok=True)
    install_fonts()
    tl = json.loads((DAY / "timeline.json").read_text(encoding="utf-8"))
    total = tl["total_frames"]
    workers = int(os.environ.get("ABIT_WORKERS", "0")) or max(1, (os.cpu_count() or 2) - 0)
    workers = min(workers, 2 if (os.cpu_count() or 2) <= 2 else (os.cpu_count() or 2) - 1)
    silent = VIDEO / "video-only.mp4"
    if silent.exists():
        silent.unlink()

    last = [0.0]

    def progress(done, tot, elapsed):
        now = time.time()
        if now - last[0] < 2.0 and done < tot:
            return
        last[0] = now
        pct = 100.0 * done / tot
        rate = done / max(1e-6, elapsed)
        eta = (tot - done) / max(1e-6, rate)
        print(f"  frame {done:>5}/{tot}  {pct:5.1f}%  {rate:4.1f} fps  eta {eta:5.0f}s",
              flush=True)

    print(f"rendering {total} frames at {T.W}x{T.H} using {workers} worker(s)")
    t0 = time.time()
    render_to_ffmpeg(silent, str(DAY / "timeline.json"), workers=workers,
                     chunk=8, progress=progress)
    dt = time.time() - t0
    print(f"  video encode done in {dt / 60:.1f} min "
          f"({total / max(dt, 1e-6):.1f} fps)")

    final, music_only = deliver(
        silent, DAY / "audio" / "master_final.wav",
        DAY / "audio" / "master_music_sfx_only.wav", VIDEO)
    print(f"  {final}  ({final.stat().st_size / 1e6:.1f} MB)")
    print(f"  {music_only}  ({music_only.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())