#!/usr/bin/env python3
"""
A Bit Inside - video/audio muxing (section 9).

The renderer produces a silent, fully encoded video-only file. This module attaches
the mastered audio twice: once to the full mix and once to the no-narration mix,
producing the two deliverables without re-encoding the picture.

The muxer itself is channel-independent and now lives in `videokit.mux`; this
module keeps the channel's publish-naming policy and re-exports `mux` unchanged.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[4]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from videokit.mux import FFMPEG, mux  # noqa: E402,F401  (shared with every channel)


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