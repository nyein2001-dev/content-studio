#!/usr/bin/env python3
"""Render the silent video and attach the mastered audio.

Frames go straight to FFmpeg's stdin as raw RGB. No PNG sequence ever touches
the disk except the Manim layers, which live in a temp directory that is removed
afterwards.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3]))

import theme as T  # noqa: E402
import scenes as S  # noqa: E402
from videokit import engine as E  # noqa: E402

DAY = HERE.parent
VIDEO = DAY / "video"
TL = json.loads((DAY / "timeline.json").read_text(encoding="utf-8"))
AUDIO = DAY / "audio"


def compose(cr, frame: int) -> None:
    S.compose_frame(cr, frame, TL)


def main() -> int:
    VIDEO.mkdir(parents=True, exist_ok=True)
    silent = VIDEO / "video-only.mp4"
    total = TL["total_frames"]

    # Manim is optional: if it cannot render, charts and counters fall back to
    # pycairo with identical easing, and the fallback is logged for qa-report.md.
    manim_note = "not required for this build (no Manim chart scenes)"
    tmp = Path(tempfile.mkdtemp(prefix="manim-", dir=str(DAY.parent / ".cache")))
    try:
        t0 = time.time()

        def progress(done, tot, el):
            rate = done / max(el, 1e-6)
            left = (tot - done) / max(rate, 1e-6)
            print(f"\r  frame {done}/{tot}  {rate:.1f} fps  eta {left:5.0f}s",
                  end="", flush=True)

        E.render_to_ffmpeg(silent, total, compose, progress=progress)
        el = time.time() - t0
        print(f"\r  rendered {total} frames in {el:.1f}s ({total/el:.1f} fps)      ")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"  video-only: {silent.stat().st_size/1e6:.1f} MB")

    master = AUDIO / "master_final.wav"
    if not master.is_file():
        print("  master_final.wav missing; run audio mix first")
        return 1
    from videokit.mux import mux

    final = VIDEO / "sample-final.mp4"
    mux(silent, master, final)
    print(f"  final: {final} ({final.stat().st_size/1e6:.1f} MB)")
    (DAY / "render_notes.json").write_text(json.dumps(
        {"frames": total, "seconds": round(total / T.FPS, 3), "fps": T.FPS,
         "manim": manim_note, "encode": " ".join(E.ENCODE_FLAGS)}, indent=2),
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
