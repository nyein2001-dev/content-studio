"""Seeded stress. A clean LayoutError is a pass. A solved scene may not keep a violation."""
from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from layout.dsl import load_scene  # noqa: E402
from layout.errors import LayoutError  # noqa: E402
from layout.rules import check_scene, hard_failures  # noqa: E402
from layout.solver import solve  # noqa: E402
from layout.spec import load_spec  # noqa: E402


def _scene(profile: str, labels: list[str], counter: str | None) -> dict:
    stage = [{
        "id": "chips",
        "type": "chip_row",
        "labels": labels,
        "alternate": "vertical",
    }]
    if counter is not None:
        stage.insert(0, {
            "id": "count",
            "type": "stat",
            "title": "CASES",
            "value": "1",
            "max_value": counter,
        })
    return {
        "id": f"fuzz-{profile}-{len(labels)}",
        "profile": profile,
        "duration_s": 3.0,
        "splittable": False,
        "brand": "A Bit Inside",
        "headline": "MEASURED",
        "caption": "one line",
        "footnote": "ILLUSTRATIVE",
        "stage": stage,
    }


class FuzzTests(unittest.TestCase):
    def test_seeded_profiles_do_not_pass_with_a_violation(self):
        spec = load_spec()
        rng = random.Random(int(spec["fuzz_seed"]))
        profiles = ["portrait"]
        glyphs = ["IIII", "WWWW", "COPELAND XWEB", "W" * rng.randint(6, 12)]
        counters = [None, "9", "999999"]
        for profile in profiles:
            for count in range(1, 5):
                for glyph in glyphs:
                    labels = [glyph if index == 0 else f"N{index}" for index in range(count)]
                    rng.shuffle(labels)
                    for counter in counters:
                        doc = _scene(profile, labels, counter)
                        try:
                            placed = solve(doc)
                        except LayoutError:
                            continue
                        for scene in placed:
                            hard = hard_failures(check_scene(scene))
                            self.assertFalse(
                                hard,
                                f"{doc['id']} passed with {[item.rule for item in hard]}",
                            )

    def test_five_hundred_scenes_inside_the_limits_pass(self):
        rng = random.Random(20261014)
        labels = ["AK-SM", "AK-SC", "PROBES", "TARGET", "DEFROST"]
        for index in range(500):
            doc = _scene("portrait", [rng.choice(labels)], None)
            doc["id"] = f"fuzz500-{index}"
            doc["headline"] = rng.choice(["FIFTY DEGREES", "ONE BOX", "YOUR TURN"])
            placed = solve(doc)
            hard = hard_failures(check_scene(placed[0]))
            self.assertFalse(hard, f"{doc['id']} {[item.rule for item in hard]}")

    def test_over_limit_names_the_field_and_the_limit(self):
        doc = _scene("portrait", ["THIS LABEL IS WAY TOO LONG"], None)
        with self.assertRaises(LayoutError) as caught:
            solve(doc)
        self.assertIn("18", str(caught.exception))
        self.assertIn("chip", str(caught.exception).lower())
        path = ROOT / "layout" / "templates" / "stress" / "chips.yaml"
        scene = solve(load_scene(path))[0]
        self.assertFalse(hard_failures(check_scene(scene)))


if __name__ == "__main__":
    unittest.main()
