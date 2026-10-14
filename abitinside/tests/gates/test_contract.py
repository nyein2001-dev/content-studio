"""Measure, centering, slots, timeline, and the episode contact sheet."""
from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from layout.debug import contact_sheet  # noqa: E402
from layout.dsl import load_scene  # noqa: E402
from layout.solver import solve  # noqa: E402
from layout.text import measure, raster  # noqa: E402

DAY = ROOT / "2026-10-13"
HASH_PATH = ROOT / "tests" / "fixtures" / "layout" / "contact_sheet.sha256"


class MeasureTests(unittest.TestCase):
    def test_measure_matches_the_raster_within_one_pixel(self):
        ink = measure("FIFTY", "bold", 72)
        image = raster("FIFTY", "bold", 72, (255, 255, 255))
        alpha = np.array(image.split()[-1])
        ys, xs = np.where(alpha > 16)
        self.assertLessEqual(abs((xs.max() - xs.min() + 1) - ink.width), 1.0)
        self.assertLessEqual(abs((ys.max() - ys.min() + 1) - ink.height), 1.0)


class CenteringTests(unittest.TestCase):
    def test_chip_ink_is_centered_within_two_pixels(self):
        scene = solve(load_scene(DAY / "scenes" / "the_reveal.yaml"))[0]
        by_id = scene.by_id()
        chips = [node for node in scene.nodes if node.kind == "chip"]
        self.assertTrue(chips)
        for chip in chips:
            labels = []
            for node in scene.nodes:
                if node.kind != "text" or node.ink is None:
                    continue
                parent = by_id.get(node.parent or "")
                if parent is not None and parent.parent == chip.id:
                    labels.append(node)
            self.assertTrue(labels, chip.id)
            for label in labels:
                self.assertLessEqual(abs(label.ink.cx - chip.rect.cx), 2.0)
                self.assertLessEqual(abs(label.ink.cy - chip.rect.cy), 2.0)


class SlotTests(unittest.TestCase):
    def test_shared_slot_waits_for_the_handover_gap(self):
        scene = solve(load_scene(DAY / "scenes" / "the_flaw.yaml"))[0]
        windows = sorted({
            (node.motion.start, node.motion.end)
            for node in scene.nodes
            if node.motion and node.motion.slot == "auth"
        })
        self.assertGreaterEqual(len(windows), 2)
        gap = 0.1 * scene.fps
        for left, right in zip(windows, windows[1:]):
            self.assertGreaterEqual(right[0] - left[1], gap - 0.51)


class TimelineTests(unittest.TestCase):
    def test_labels_alternate_around_the_axis(self):
        scene = solve(load_scene(DAY / "scenes" / "legacy.yaml"))[0]
        axis = next(node for node in scene.nodes if node.role == "axis")
        labels = [node for node in scene.nodes if node.kind == "tick_label"]
        self.assertGreaterEqual(len(labels), 2)
        above = [node for node in labels if node.rect.bottom <= axis.rect.y]
        below = [node for node in labels if node.rect.y >= axis.rect.bottom]
        self.assertTrue(above)
        self.assertTrue(below)


class GoldenTests(unittest.TestCase):
    def test_episode_contact_sheet_hash(self):
        scenes = [solve(load_scene(path))[0] for path in sorted((DAY / "scenes").glob("*.yaml"))]
        dest = ROOT / "out" / "draft" / "2026-10-13" / "contact_sheet.png"
        contact_sheet(scenes, dest)
        digest = hashlib.sha256(dest.read_bytes()).hexdigest()
        expected = HASH_PATH.read_text(encoding="utf-8").strip()
        self.assertEqual(digest, expected, dest)


if __name__ == "__main__":
    unittest.main()
