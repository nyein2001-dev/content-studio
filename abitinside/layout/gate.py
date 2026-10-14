"""Publish gate, certificate, and draft promotion."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from layout.debug import annotate, contact_sheet, debug_frame
from layout.errors import LayoutError
from layout.lint import lint_sources
from layout.model import PlacedScene
from layout.parity import check_parity, write_video
from layout.pixels import check_pixels
from layout.report import dump_json, scene_report, write_html, write_markdown
from layout.rules import Violation, check_scene, hard_failures
from layout.solver import solve
from layout.spec import ABIT, load_spec
from layout.swept import check_swept


def video_hash(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def certificate_path(directory: Path) -> Path:
    return directory / "layout_certificate.json"


def write_certificate(directory: Path, video: Path, passed: dict) -> dict:
    spec = load_spec()
    payload = {
        "spec_version": spec["version"],
        "validator_version": spec["validator_version"],
        "video_sha256": video_hash(video),
        "video_name": video.name,
        "passed": passed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    dump_json(certificate_path(directory), payload)
    return payload


def assert_certified(video: Path) -> None:
    """Refuse an upload or metadata stamp when the certificate is missing or stale."""
    video = Path(video)
    cert = certificate_path(video.parent)
    if not cert.is_file():
        raise SystemExit(
            f"refusing {video.name}: no layout_certificate.json beside it. "
            "Run python -m layout gate. Uncertified files cannot be published."
        )
    data = json.loads(cert.read_text(encoding="utf-8"))
    spec = load_spec()
    if data.get("spec_version") != spec["version"]:
        raise SystemExit(
            f"refusing {video.name}: certificate spec {data.get('spec_version')} "
            f"does not match {spec['version']}."
        )
    if data.get("video_sha256") != video_hash(video) or data.get("video_name") != video.name:
        raise SystemExit(
            f"refusing {video.name}: certificate hash does not match the file. "
            "The file was replaced after the gate. Run the gate again."
        )
    passed = data.get("passed") or {}
    if not passed or not all(passed.values()):
        raise SystemExit(f"refusing {video.name}: certificate records a failed gate.")


def promote(draft: Path, publish: Path) -> None:
    publish.parent.mkdir(parents=True, exist_ok=True)
    staging = publish.parent / f".{publish.name}.staging"
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(draft, staging)
    backup = publish.parent / f".{publish.name}.backup"
    if backup.exists():
        shutil.rmtree(backup)
    if publish.exists():
        publish.rename(backup)
    try:
        staging.rename(publish)
    except OSError:
        if backup.exists() and not publish.exists():
            backup.rename(publish)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def gate_documents(
    docs: list[dict],
    draft: Path,
    publish: Path | None,
    preset: str | None = None,
    pixels: bool = True,
    parity: bool = True,
) -> int:
    placed: list[PlacedScene] = []
    reports = []
    annotated: list[tuple[PlacedScene, Violation]] = []
    ok = True
    lint = lint_sources()
    if lint:
        ok = False
        reports.append({
            "scene": "lint",
            "profile": "",
            "legacy": False,
            "duration_frames": 0,
            "decisions": [],
            "violations": [
                Violation("lint", "R15", "fail", item, "Remove the coordinate or drawing call.", ()).as_dict()
                for item in lint
            ],
        })
    for doc in docs:
        try:
            solved = solve(doc)
        except LayoutError as exc:
            ok = False
            reports.append({
                "scene": exc.scene,
                "profile": doc.get("profile", ""),
                "legacy": False,
                "duration_frames": 0,
                "decisions": [],
                "violations": [Violation(
                    exc.scene, exc.rule, "fail", exc.message, exc.remedy, (), measured=exc.measured,
                ).as_dict()],
            })
            continue
        for scene in solved:
            print(f"check {scene.scene_id}", flush=True)
            found = check_scene(scene)
            found.extend(check_swept(scene))
            if pixels:
                found.extend(check_pixels(scene))
            if hard_failures(found):
                ok = False
            reports.append(scene_report(scene, found))
            placed.append(scene)
            annotated.extend((scene, item) for item in found if item.severity == "fail")
    draft.mkdir(parents=True, exist_ok=True)
    dump_json(draft / "layout_report.json", {"passed": ok, "scenes": reports})
    dump_json(draft / "qa_report.json", {"passed": ok, "scenes": reports})
    write_markdown(draft / "qa_report.md", reports)
    frames = []
    for scene in placed:
        image = debug_frame(scene)
        dest = draft / f"{scene.scene_id}.png"
        image.save(dest)
        frames.append(dest)
    for index, (scene, item) in enumerate(annotated):
        annotate(scene, item).save(draft / f"violation-{scene.scene_id}-{item.rule}-{index}.png")
    if placed:
        contact_sheet(placed, draft / "contact_sheet.png")
        debug_frame(placed[0]).save(draft / "thumbnail.png")
    write_html(draft / "layout_report.html", "Layout gate", reports, frames)
    if not ok or not placed:
        return 1
    video = draft / "video.mp4"
    print(f"encode {sum(scene.duration_frames for scene in placed)} frames", flush=True)
    write_video(placed, video, preset=preset)
    if parity:
        extra = []
        offset = 0
        spec = load_spec()
        for scene in placed:
            visible = min(scene.duration_frames - 1, int(spec["rules"]["enter_frames"]))
            extra.extend(check_parity(scene, video, frames=[visible], video_offset=offset))
            offset += scene.duration_frames
        if hard_failures(extra):
            reports.append(scene_report(placed[0], extra))
            dump_json(draft / "layout_report.json", {"passed": False, "scenes": reports})
            return 1
    passed = {"lint": True, "static": True, "swept": True, "pixels": pixels, "parity": parity, "budget": True}
    write_certificate(draft, video, passed)
    dump_json(draft / "layout_report.json", {"passed": True, "scenes": reports})
    dump_json(draft / "qa_report.json", {"passed": True, "scenes": reports})
    write_markdown(draft / "qa_report.md", reports)
    if publish is not None:
        promote(draft, publish)
    return 0
