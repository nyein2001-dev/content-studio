"""Machine and author-facing reports."""
from __future__ import annotations

import json
from pathlib import Path

from layout.model import PlacedScene
from layout.rules import Violation


def dump_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def scene_report(scene: PlacedScene, violations: list[Violation]) -> dict:
    return {
        "scene": scene.scene_id,
        "profile": scene.profile,
        "legacy": scene.legacy,
        "duration_frames": scene.duration_frames,
        "decisions": [{"action": item.action, "detail": item.detail} for item in scene.decisions],
        "violations": [item.as_dict() for item in violations],
    }


def write_html(path: Path, title: str, reports: list[dict], images: list[Path]) -> None:
    rows = []
    for report in reports:
        for item in report["violations"]:
            if item["severity"] == "warn":
                continue
            rows.append(
                "<tr>"
                f"<td>{_esc(report['scene'])}</td>"
                f"<td>{_esc(item['rule'])}</td>"
                f"<td>{item.get('frame')}</td>"
                f"<td>{_esc(item['message'])}</td>"
                f"<td>{_esc(item['remedy'])}</td>"
                "</tr>"
            )
    pics = "\n".join(f'<img src="{_esc(path.name)}" alt="annotated frame">' for path in images)
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{_esc(title)}</title>
<style>
body {{ font: 16px sans-serif; background: #060d20; color: #fff; }}
td, th {{ border: 1px solid #2a5580; padding: 8px; vertical-align: top; }}
img {{ width: 180px; margin: 8px; }}
</style></head><body>
<h1>{_esc(title)}</h1>
<p>Each row is one hard failure. Fix the scene DSL, then run the gate again.</p>
<table><thead><tr><th>Scene</th><th>Rule</th><th>Frame</th><th>What happened</th><th>Fix</th></tr></thead>
<tbody>
{''.join(rows) or '<tr><td colspan="5">No hard failures.</td></tr>'}
</tbody></table>
{pics}
</body></html>
"""
    path.write_text(html, encoding="utf-8")


def _esc(value) -> str:
    return (str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
