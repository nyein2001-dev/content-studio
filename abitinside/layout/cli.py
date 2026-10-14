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

    render = sub.add_parser("render")
    render.add_argument("--video", type=Path, required=True)
    render.add_argument("--debug-zones", action="store_true")
    render.add_argument("--preset")

    validate = sub.add_parser("validate")
    validate.add_argument("--video", type=Path)
    validate.add_argument("--scene", type=Path)

    qa = sub.add_parser("qa")
    qa.add_argument("--video", type=Path, required=True)
    qa.add_argument("--debug-zones", action="store_true")

    publish = sub.add_parser("publish")
    publish.add_argument("--video", type=Path, required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            return _check(args)
        if args.command == "validate":
            return _validate(args.video or args.scene)
        if args.command == "render":
            return _render(args)
        if args.command == "qa":
            return _qa(args)
        if args.command == "publish":
            return _publish(args)
        return _gate(args)
    except LayoutError as exc:
        print(f"{exc.scene}: {exc.rule}: {exc.message}\nFix: {exc.remedy}", file=sys.stderr)
        return 1


def _output_name(path: Path) -> str:
    """A video.yaml lives in the day folder, so the release uses that day."""
    if path.name.startswith("video"):
        return path.parent.name
    return path.stem


def _documents(path: Path) -> list[dict]:
    if path.name.startswith("video"):
        return load_video(path)["scene_docs"]
    return [load_scene(path)]


def _validate(path: Path | None) -> int:
    if path is None:
        root = ABIT / "layout" / "templates"
        paths = list(root.glob("*.yaml")) + list((root / "stress").glob("*.yaml"))
        code = 0
        for item in paths:
            if _validate(item):
                code = 1
        return code
    docs = _documents(path)
    code = 0
    for doc in docs:
        for scene in solve(doc):
            found = hard_failures(check_scene(scene) + check_swept(scene))
            for item in found:
                print(f"{item.scene} {item.rule} frame={item.frame}: {item.message}")
            if found:
                code = 1
    return code


def _render(args) -> int:
    if _validate(args.video):
        print("validate failed; render did not start", file=sys.stderr)
        return 1
    docs = _documents(args.video)
    scenes = [scene for doc in docs for scene in solve(doc)]
    from layout.parity import write_video
    out = ABIT / "out" / "draft" / _output_name(args.video)
    out.mkdir(parents=True, exist_ok=True)
    video = out / "video.mp4"
    spec = load_spec()
    write_video(scenes, video, preset=args.preset or spec["encode"]["perf_preset"])
    if args.debug_zones:
        from layout.debug import debug_frame
        for scene in scenes:
            debug_frame(scene).save(out / f"{scene.scene_id}-zones.png")
    if _validate(args.video):
        print("validate failed after render", file=sys.stderr)
        return 1
    print(video)
    return 0


def _qa(args) -> int:
    spec = load_spec()
    draft = ABIT / "out" / "draft" / _output_name(args.video)
    docs = _documents(args.video)
    code = gate_documents(docs, draft, None, preset=spec["encode"]["perf_preset"], parity=False)
    from layout.debug import contact_sheet
    scenes = []
    if code == 0:
        scenes = [scene for doc in docs for scene in solve(doc)]
        contact_sheet(scenes, draft / "contact_sheet.png")
    return code


def _publish(args) -> int:
    spec = load_spec()
    draft = ABIT / "out" / "draft" / _output_name(args.video)
    publish = ABIT / "out" / "publish" / _output_name(args.video)
    docs = _documents(args.video)
    code = gate_documents(docs, draft, None, preset=spec["encode"]["preset"])
    report = draft / "qa_report.json"
    video = draft / "video.mp4"
    if code != 0 or not report.is_file() or not video.is_file():
        print("publish refused: validation errors", file=sys.stderr)
        return 1
    if report.stat().st_mtime < video.stat().st_mtime:
        print("publish refused: qa report is older than the video", file=sys.stderr)
        return 1
    from layout.gate import promote
    _release_metadata(args.video, draft)
    promote(draft, publish)
    print(publish)
    return 0


def _release_metadata(video: Path, draft: Path) -> None:
    """Copy the title, caption, and hashtags the publish folder is required to carry."""
    day = video.resolve().parent
    meta_path = day / "youtube-metadata.json"
    if not meta_path.is_file():
        return
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    (draft / "title.txt").write_text(str(meta.get("title") or "") + "\n", encoding="utf-8")
    (draft / "caption.txt").write_text(str(meta.get("description") or "") + "\n", encoding="utf-8")
    tags = meta.get("hashtags") or []
    (draft / "hashtags.txt").write_text("\n".join(tags) + "\n", encoding="utf-8")


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
    draft = args.draft or (ABIT / "out" / "draft" / _output_name(args.video))
    publish = args.publish or (ABIT / "out" / "publish" / _output_name(args.video))
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
