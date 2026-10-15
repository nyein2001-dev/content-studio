#!/usr/bin/env python3
"""Shared muxing. Video is never re-encoded: the picture stream is copied and
only AAC audio is attached."""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

FFMPEG = os.environ.get("FFMPEG", "ffmpeg")


def mux(video_in: Path, audio_in: Path, out: Path, *,
       bitrate: str = "192k", rate: int = 48000, channels: int = 2) -> None:
    """Mux into a sibling temp file, then atomically replace the target.

    Writing beside the target and renaming afterwards avoids the "permission
    denied" that Windows raises while a previous file is still mapped.
    """
    tmp = out.with_suffix(".muxing.mp4")
    if tmp.exists():
        tmp.unlink()
    cmd = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(video_in), "-i", str(audio_in),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", bitrate,
        "-ar", str(rate), "-ac", str(channels),
        "-movflags", "+faststart", "-shortest", str(tmp),
    ]
    last = ""
    for attempt in range(4):
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0 and tmp.exists():
            break
        last = r.stderr[:600]
        time.sleep(2.0 * (attempt + 1))
    else:
        raise RuntimeError(f"mux failed after 4 attempts: {last}")

    for attempt in range(4):
        try:
            if out.exists():
                out.unlink()
            os.replace(tmp, out)
            return
        except OSError as exc:
            last = str(exc)
            time.sleep(2.0 * (attempt + 1))
    raise RuntimeError(f"could not replace {out}: {last}")


def extract_wav(src: Path, dst: Path, rate: int = 48000, mono: bool = True) -> None:
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
           "-ac", "1" if mono else "2", "-ar", str(rate),
           "-c:a", "pcm_f32le", str(dst)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"extract failed: {r.stderr[-500:]}")