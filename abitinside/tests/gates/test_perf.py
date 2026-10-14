"""Three-minute validator budget. Encode time is not included.

Run with ABIT_LAYOUT_PERF=1. The Makefile `perf` target does that.
"""
from __future__ import annotations

import os
import sys
import time
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from layout.dsl import load_scene  # noqa: E402
from layout.parity import check_parity, write_video  # noqa: E402
from layout.pixels import check_pixels  # noqa: E402
from layout.rules import hard_failures  # noqa: E402
from layout.solver import solve  # noqa: E402
from layout.spec import load_spec  # noqa: E402
from layout.swept import check_swept  # noqa: E402


@unittest.skipUnless(os.environ.get("ABIT_LAYOUT_PERF") == "1", "set ABIT_LAYOUT_PERF=1")
class PerfTests(unittest.TestCase):
    def test_three_minute_validator_and_veryfast_parity_sample(self):
        spec = load_spec()
        scene = solve(load_scene(ROOT / "layout" / "templates" / "hero_chart.yaml"))[0]
        long = replace(scene, duration_frames=3 * 60 * int(spec["fps"]))
        started = time.perf_counter()
        found = check_swept(long)
        found.extend(check_pixels(long))
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 300.0, f"validator took {elapsed:.1f}s")
        self.assertFalse(hard_failures(found), [item.rule for item in hard_failures(found)])

        short = replace(scene, duration_frames=int(spec["rules"]["enter_frames"]) + 1)
        video = ROOT / "out" / "draft" / "perf" / "sample.mp4"
        write_video([short], video, preset=spec["encode"]["perf_preset"])
        parity = check_parity(short, video, frames=[short.duration_frames - 1])
        self.assertFalse(hard_failures(parity), [item.message for item in hard_failures(parity)])


if __name__ == "__main__":
    unittest.main()
