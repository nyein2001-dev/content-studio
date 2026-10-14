"""Layout engine tests."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from layout.dsl import load_scene  # noqa: E402
from layout.fit import fit_text  # noqa: E402
from layout.gate import assert_certified, write_certificate  # noqa: E402
from layout.lint import lint_sources  # noqa: E402
from layout.metrics import measure  # noqa: E402
from layout.router import route  # noqa: E402
from layout.rules import check_scene, hard_failures  # noqa: E402
from layout.solver import solve  # noqa: E402
from layout.spec import load_spec  # noqa: E402
from layout.geom import Rect  # noqa: E402
from .defects import DEFECTS as CASES  # noqa: E402


class MetricsTests(unittest.TestCase):
    def test_ink_is_not_just_the_advance(self):
        ink = measure("W", "bold", 64)
        self.assertGreater(ink.width, 10)
        self.assertGreater(ink.height, 10)

    def test_wide_glyphs_are_wider_than_narrow_ones(self):
        wide = measure("MMMM", "bold", 32)
        narrow = measure("IIII", "bold", 32)
        self.assertGreater(wide.width, narrow.width)


class FitTests(unittest.TestCase):
    def test_single_line_at_preferred_size(self):
        fitted = fit_text("t", "FIFTY DEGREES", "headline", 900)
        self.assertEqual(fitted.lines, ("FIFTY DEGREES",))
        self.assertGreaterEqual(fitted.size, 64)

    def test_does_not_ellipsis(self):
        with self.assertRaises(Exception) as caught:
            fit_text("t", "W" * 80, "chip", 120, max_lines=1)
        self.assertIn("LR-04", str(caught.exception))
        self.assertNotIn("…", str(caught.exception))


class RouterTests(unittest.TestCase):
    def test_straight_line_when_clear(self):
        path = route("t", (0, 0), (40, 0), [], Rect(0, 0, 80, 80), 8, mode="straight")
        self.assertEqual(path[0], (0, 0))
        self.assertEqual(path[-1], (40, 0))

    def test_blocked_route_fails_cleanly(self):
        from layout.errors import LayoutError
        wall = Rect(10, 0, 20, 80)
        with self.assertRaises(LayoutError) as caught:
            route("t", (0, 40), (80, 40), [wall], Rect(0, 0, 40, 40), 8)
        self.assertEqual(caught.exception.rule, "LR-06")


class RuleTests(unittest.TestCase):
    def test_each_defect_names_its_rule(self):
        for code, (builder, expected) in CASES.items():
            found = {item.rule for item in hard_failures(check_scene(builder()))}
            missing = expected - found
            self.assertFalse(missing, f"{code} missing {missing}, got {sorted(found)}")


class TemplateTests(unittest.TestCase):
    def test_templates_and_stress_pass(self):
        root = ROOT / "layout" / "templates"
        for path in list(root.glob("*.yaml")) + list((root / "stress").glob("*.yaml")):
            scene = solve(load_scene(path))[0]
            hard = hard_failures(check_scene(scene))
            self.assertFalse(hard, f"{path.name}: {[(item.rule, item.message) for item in hard]}")


class LintTests(unittest.TestCase):
    def test_sanctioned_modules_have_no_drawing_bypass(self):
        self.assertEqual(lint_sources(), [])


class CertificateTests(unittest.TestCase):
    def test_tamper_and_missing_certificate_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            video = folder / "video.mp4"
            video.write_bytes(b"abc")
            with self.assertRaises(SystemExit):
                assert_certified(video)
            write_certificate(folder, video, {"static": True})
            assert_certified(video)
            video.write_bytes(b"abd")
            with self.assertRaises(SystemExit):
                assert_certified(video)


class SpecTests(unittest.TestCase):
    def test_spec_version_and_profiles(self):
        spec = load_spec()
        self.assertEqual(spec["version"], "1.0.0")
        self.assertEqual(set(spec["profiles"]), {"portrait", "landscape", "square"})


if __name__ == "__main__":
    unittest.main()
