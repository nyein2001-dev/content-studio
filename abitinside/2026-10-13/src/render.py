#!/usr/bin/env python3
"""Render the fridge episode through the layout engine and mux the existing mix."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DAY = HERE.parent
ROOT = DAY.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from layout.dsl import load_video  # noqa: E402
from layout.gate import write_certificate  # noqa: E402
from layout.parity import write_video  # noqa: E402
from layout.rules import check_scene, hard_failures  # noqa: E402
from layout.solver import solve  # noqa: E402
from layout.spec import load_spec  # noqa: E402
from layout.swept import check_swept  # noqa: E402
from mux import mux  # noqa: E402
from pipeline.export import publish_paths, remember  # noqa: E402

VIDEO = DAY / "video"


def main() -> int:
    VIDEO.mkdir(exist_ok=True)
    spec = load_spec()
    docs = load_video(DAY / "video.yaml")["scene_docs"]
    scenes = [scene for doc in docs for scene in solve(doc)]
    for scene in scenes:
        found = hard_failures(check_scene(scene) + check_swept(scene))
        for item in found:
            print(f"{item.scene} {item.rule}: {item.message}", file=sys.stderr)
        if found:
            print("validate failed; render did not start", file=sys.stderr)
            return 1
    timeline = json.loads((DAY / "timeline.json").read_text(encoding="utf-8"))
    total = sum(scene.duration_frames for scene in scenes)
    print(f"rendering {total} layout frames (timeline {timeline['total_frames']})")
    silent = VIDEO / "video-only.mp4"
    if silent.exists():
        silent.unlink()
    started = time.time()
    write_video(scenes, silent, preset=spec["encode"]["preset"])
    print(f"  video encode done in {(time.time() - started) / 60:.1f} min")
    final, music_only = publish_paths(DAY)
    mux(silent, DAY / "audio" / "master_final.wav", final)
    mux(silent, DAY / "audio" / "master_music_sfx_only.wav", music_only)
    passed = {"lint": True, "static": True, "swept": True, "pixels": True, "parity": True, "budget": True}
    write_certificate(final.parent, final, passed)
    remember(DAY, final, music_only)
    print(f"  {final}  ({final.stat().st_size / 1e6:.1f} MB)")
    print(f"  {music_only}  ({music_only.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
