#!/usr/bin/env python3
"""Stamp the measured technical block into the YouTube package.

The duration, loudness and file size in the upload package were hand written
once and then went stale the first time the video was re-rendered. This reads
them off the delivered file instead, so the package an uploader reads always
describes the MP4 that actually exists.

Run after mux and after the mix, as the last step of the build.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

DAY = Path(__file__).resolve().parent.parent
FFMPEG = Path(os.environ["FFMPEG"])
FFPROBE = Path(os.environ.get("FFPROBE", FFMPEG.with_name("ffprobe")))
VIDEO = DAY / "video" / "sample-final.mp4"
JOUT = DAY / "youtube-metadata.json"
MOUT = DAY / "youtube-metadata.md"


def probe(path: Path) -> dict:
    raw = subprocess.run(
        [str(FFPROBE), "-v", "error", "-of", "json", "-show_format", "-show_streams", str(path)],
        check=True, capture_output=True, text=True).stdout
    info = json.loads(raw)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    num, _, den = v["r_frame_rate"].partition("/")
    return {
        "width": v["width"],
        "height": v["height"],
        "fps": round(int(num) / int(den)),
        "duration_seconds": round(float(info["format"]["duration"]), 3),
        "video_codec": f"{v['codec_name']} {v['profile']} {v['pix_fmt']}",
        "audio_codec": (f"{a['codec_name']} {round(int(a['bit_rate']) / 1000)} kbps "
                        f"{a['sample_rate']} Hz {'stereo' if a['channels'] == 2 else 'mono'}"),
        "size_mb": round(float(info["format"]["size"]) / 1e6, 1),
    }


def main() -> int:
    if not VIDEO.exists():
        print(f"no {VIDEO}, nothing to stamp")
        return 1
    tech = probe(VIDEO)

    loud_path = DAY / "audio" / "loudness.json"
    if loud_path.exists():
        loud = json.loads(loud_path.read_text(encoding="utf-8"))
        tech["integrated_lufs"] = loud["integrated_lufs"]
        tech["true_peak_dbtp"] = loud["true_peak_dbtp"]

    if JOUT.exists():
        doc = json.loads(JOUT.read_text(encoding="utf-8"))
        before = dict(doc.get("technical", {}))
        doc["technical"] = {**before, **tech}
        JOUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        for key in ("duration_seconds", "size_mb", "integrated_lufs", "true_peak_dbtp"):
            if key in before and before[key] != tech.get(key):
                print(f"  corrected {key}: {before[key]} -> {tech.get(key)}")
        print(f"  stamped {JOUT.name}")

    if MOUT.exists():
        md = MOUT.read_text(encoding="utf-8")
        mins, secs = divmod(tech["duration_seconds"], 60)
        stamp = (f"**File:** `video/sample-final.mp4` \u00b7 {tech['width']}x{tech['height']} \u00b7 "
                 f"{tech['fps']} fps \u00b7 {int(mins)}:{secs:04.1f} \u00b7 {tech['size_mb']} MB")
        new = re.sub(r"^\*\*File:\*\*.*$", stamp.replace("\\", "\\\\"), md, count=1, flags=re.M)
        if new != md:
            MOUT.write_text(new, encoding="utf-8")
            print(f"  stamped {MOUT.name} -> {int(mins)}:{secs:04.1f}, {tech['size_mb']} MB")

    print(f"duration {tech['duration_seconds']:.3f}s  {tech['width']}x{tech['height']}  "
          f"{tech['fps']}fps  {tech['video_codec']}  {tech['audio_codec']}  "
          f"{tech['size_mb']} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())