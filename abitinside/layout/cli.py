"""layout-check and the publish gate."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from layout.budget import check_budget
from layout.dsl import load_scene, load_video
from layout.errors import LayoutError
from layout.gate import gate_documents
from layout.legacy import probe_episode
from layout.lint import lint_sources
from layout.pixels import check_pixels
from layout.report import dump_json, scene_report, write_html
from layout.rules import check_scene, hard_failures
from layout.solver import solve
from layout.spec import ABIT, load_spec
from layout.swept import check_swept


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="layout")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check")
    check.add_argument("which", choices=["static", "swept", "pixels", "parity", "lint", "budget"])
    check.add_argument("--scene", type=Path)

    gate = sub.add_parser("gate")
    gate.add_argument("--video", type=Path)
    gate.add_argument("--showcase", action="store_true")
    gate.add_argument("--sample", action="store_true")
    gate.add_argument("--preset")
    gate.add_argument("--draft", type=Path)
    gate.add_argument("--publish", type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            return _check(args)
        return _gate(args)
    except LayoutError as exc:
        print(f"{exc.scene}: {exc.rule}: {exc.message}\nFix: {exc.remedy}", file=sys.stderr)
        return 1


def _check(args) -> int:
    if args.which == "lint":
        problems = lint_sources()
        for item in problems:
            print(item)
        return 1 if problems else 0
    if args.scene is None:
        print("pass --scene", file=sys.stderr)
        return 2
    doc = load_scene(args.scene)
    if args.which == "budget":
        problems = check_budget(doc)
        for item in problems:
            print(item)
        return 1 if problems else 0
    solved = solve(doc)
    code = 0
    for scene in solved:
        if args.which == "static":
            found = check_scene(scene)
        elif args.which == "swept":
            found = check_swept(scene)
        elif args.which == "pixels":
            found = check_pixels(scene)
        else:
            print("parity runs inside the gate, after the file is encoded", file=sys.stderr)
            return 2
        hard = hard_failures(found)
        for item in hard:
            print(f"{item.scene} {item.rule} frame={item.frame}: {item.message}")
            print(f"  Fix: {item.remedy}")
        if hard:
            code = 1
    return code


def _gate(args) -> int:
    spec = load_spec()
    if args.sample:
        return _sample()
    if args.showcase:
        video = ABIT / "examples" / "layout_showcase" / "video.yaml"
        draft = args.draft or (ABIT / "out" / "draft" / "layout_showcase")
        publish = args.publish or (ABIT / "out" / "publish" / "layout_showcase")
        docs = load_video(video)["scene_docs"]
        code = gate_documents(docs, draft, publish, preset=args.preset or spec["encode"]["preset"])
        if code == 0:
            from layout.debug import contact_sheet
            from layout.solver import solve as _solve
            scenes = [scene for doc in docs for scene in _solve(doc)]
            contact_sheet(scenes, ABIT / "examples" / "layout_showcase" / "contact-sheet.png")
        return code
    if args.video is None:
        print("pass --video, --showcase, or --sample", file=sys.stderr)
        return 2
    docs = load_video(args.video)["scene_docs"] if args.video.name.startswith("video") else [load_scene(args.video)]
    draft = args.draft or (ABIT / "out" / "draft" / args.video.stem)
    publish = args.publish or (ABIT / "out" / "publish" / args.video.stem)
    return gate_documents(docs, draft, publish, preset=args.preset)


def _sample() -> int:
    draft = ABIT / "out" / "draft" / "sample-rejection"
    draft.mkdir(parents=True, exist_ok=True)
    try:
        scenes = probe_episode()
    except Exception as exc:
        payload = {
            "passed": False,
            "scenes": [{
                "scene": "2026-10-13",
                "violations": [{
                    "scene": "2026-10-13",
                    "rule": "LEGACY-UNMIGRATED",
                    "severity": "fail",
                    "message": f"legacy probe failed: {exc}",
                    "remedy": "Keep the episode frozen and fix the probe environment (cairo, fonts).",
                    "element_ids": [],
                    "frame": None,
                    "measured": {},
                }],
            }],
        }
        dump_json(draft / "layout_report.json", payload)
        print(payload["scenes"][0]["violations"][0]["message"], file=sys.stderr)
        return 1
    reports = []
    rules = set()
    for scene in scenes:
        found = check_scene(scene)
        reports.append(scene_report(scene, found))
        for item in found:
            if item.severity == "fail":
                rules.add(item.rule)
                print(f"{scene.scene_id} {item.rule}: {item.message}")
    payload = {"passed": False, "rules": sorted(rules), "scenes": reports}
    dump_json(draft / "layout_report.json", payload)
    write_html(draft / "layout_report.html", "Sample rejected", reports, [])
    fixture = ABIT / "tests" / "fixtures" / "layout" / "sample_rejection"
    dump_json(fixture / "layout_report.json", {"passed": False, "rules": sorted(rules)})
    print("REJECTED", ", ".join(sorted(rules)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
