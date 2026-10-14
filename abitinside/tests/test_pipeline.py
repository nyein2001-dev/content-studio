"""Shared pipeline tests. They use synthetic phrases, not a day's scenes."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.captions import build_groups, text_width, visible_runs  # noqa: E402
from pipeline.config import require_voice  # noqa: E402
from pipeline.export import slugify  # noqa: E402
from pipeline.layout import Box, collisions  # noqa: E402
from pipeline.brain.guard import duplicate_reason  # noqa: E402


class CaptionTests(unittest.TestCase):
    def test_spaces_are_drawn_between_words(self):
        group = {
            "frame": 10,
            "end_frame": 40,
            "text": "supermarket fridges",
            "words": [
                {"text": "supermarket", "frame": 10, "end_frame": 24},
                {"text": "fridges", "frame": 24, "end_frame": 40},
            ],
        }
        runs, _ease = visible_runs(group, 12)
        self.assertEqual([piece for piece, _colour in runs], ["supermarket", " ", "fridges"])
        self.assertGreater(text_width("supermarket fridges"), text_width("supermarketfridges") + 8)

    def test_caption_holds_until_the_last_word_ends(self):
        groups = build_groups([{
            "scene": "hook",
            "start_seconds": 1.0,
            "words": [
                {"text": "controller's", "t_start": 0.0, "t_end": 0.4},
                {"text": "own", "t_start": 0.4, "t_end": 0.7},
            ],
        }])
        group = groups[0]
        self.assertEqual(group["text"], "controller's own")
        self.assertGreaterEqual(group["end_frame"], group["words"][-1]["end_frame"])
        self.assertIn("'", group["text"])
        still_up, _ease = visible_runs(group, group["words"][-1]["end_frame"] - 1)
        self.assertIsNotNone(still_up)

    def test_punctuation_stays_on_the_word(self):
        groups = build_groups([{
            "scene": "setup",
            "start_seconds": 0.0,
            "words": [
                {"text": "probes,", "t_start": 0.0, "t_end": 0.3},
                {"text": "holds", "t_start": 0.3, "t_end": 0.6},
            ],
        }])
        self.assertEqual(groups[0]["text"], "probes, holds")

    def test_highlight_follows_the_spoken_word(self):
        group = {
            "frame": 0,
            "end_frame": 30,
            "text": "normal scheduled",
            "words": [
                {"text": "normal", "frame": 0, "end_frame": 12},
                {"text": "scheduled", "frame": 12, "end_frame": 30},
            ],
        }
        early, _ease = visible_runs(group, 4, ink="#fff", accent="#ff0")
        late, _ease = visible_runs(group, 16, ink="#fff", accent="#ff0")
        self.assertEqual(early[0][1], "#ff0")
        self.assertEqual(early[2][1], "#fff")
        self.assertEqual(late[2][1], "#ff0")


class VoiceTests(unittest.TestCase):
    def test_only_andrew_is_accepted(self):
        require_voice("en-US-AndrewNeural")
        with self.assertRaises(SystemExit):
            require_voice("en_US-ryan-high")
        with self.assertRaises(SystemExit):
            require_voice("en-US-GuyNeural")


class LayoutTests(unittest.TestCase):
    def test_label_on_its_node_is_allowed(self):
        bad = collisions([
            Box("probe", 100, 100, 80, 40, "illustration"),
            Box("probe-label", 110, 110, 40, 20, "label", label_of="probe"),
        ])
        self.assertEqual(bad, [])

    def test_caption_on_headline_is_rejected(self):
        bad = collisions([
            Box("headline", 200, 360, 400, 80, "headline"),
            Box("caption", 220, 400, 200, 40, "caption"),
        ])
        self.assertEqual(bad, [("headline", "caption")])


class ExportTests(unittest.TestCase):
    def test_slug_comes_from_the_title(self):
        self.assertEqual(
            slugify("How Hackers Heated 150 Supermarket Fridges to 50C"),
            "how-hackers-heated-150-supermarket-fridges-to-50c",
        )

    def test_meaningless_names_are_refused(self):
        with self.assertRaises(SystemExit):
            slugify("sample-final")


class HistoryTests(unittest.TestCase):
    def test_a_later_day_cannot_repeat_the_fridge_mechanism(self):
        reason = duplicate_reason(
            {"title": "Inside a refrigeration controller web interface",
             "mechanism": "refrigeration controller web interface"},
            "2026-10-14",
        )
        self.assertIsNotNone(reason)

    def test_rebuilding_the_same_day_is_allowed(self):
        reason = duplicate_reason(
            {"title": "How Hackers Heated 150 Supermarket Fridges to 50C",
             "mechanism": "refrigeration controller web interface"},
            "2026-10-13",
        )
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()
