#!/usr/bin/env python3
"""
A Bit Inside - video/audio muxing (section 9).

The renderer produces a silent, fully encoded video-only file. This module attaches
the mastered audio twice: once to the full mix and once to the no-narration mix,
producing the two deliverables without re-encoding the picture.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

FFMPEG = os.environ["FFMPEG"]


def mux(video_in: Path, audio_in: Path, out: Path) -> None:
    """Mux into a sibling temp file and then replace the target.

    Writing straight over an existing .mp4 on a Windows-mounted drive can fail with
    "Permission denied" while the previous file is still mapped by the OS or an
    indexer. Writing alongside and renaming afterwards avoids that; the delete and
    retry cover the residual case.
    """
    tmp = out.with_suffix(".muxing.mp4")
    if tmp.exists():
        tmp.unlink()
    cmd = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(video_in), "-i", str(audio_in),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", "-shortest", str(tmp),
    ]
    last = ""
    for attempt in range(4):
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0 and tmp.exists():
            break
        last = r.stderr[:500]
        time.sleep(2.0 * (attempt + 1))
    else:
        raise RuntimeError(f"mux failed after 4 attempts: {last}")

    for attempt in range(4):
        try:
            if out.exists():
                out.unlink()
            os.replace(tmp, out)
            return
        except OSError as exc:                    # Windows file lock
            last = str(exc)
            time.sleep(2.0 * (attempt + 1))
    raise RuntimeError(f"could not replace {out}: {last}")


def deliver(video_in: Path, audio_in: Path, music_audio: Path,
            video_dir: Path) -> tuple[Path, Path]:
    """Write both deliverables under the title slug and return their paths."""
    import sys
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from pipeline.export import publish_paths, remember

    day = video_dir.parent
    final, music_only = publish_paths(day)
    video_dir.mkdir(exist_ok=True)
    mux(video_in, audio_in, final)
    mux(video_in, music_audio, music_only)
    remember(day, final, music_only)
    return final, music_only


if __name__ == "__main__":
    day = Path(__file__).resolve().parent.parent
    v = day / "video"
    a, b = deliver(v / "video-only.mp4", day / "audio" / "master_final.wav",
                   day / "audio" / "master_music_sfx_only.wav", v)
    print(f"{a}  ({a.stat().st_size / 1e6:.1f} MB)")
    print(f"{b}  ({b.stat().st_size / 1e6:.1f} MB)")
    sys.exit(0)