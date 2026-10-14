"""Day-independent checks. A failed check blocks publish-ready status."""
from __future__ import annotations

import json
from pathlib import Path

from pipeline.config import VOICE_ID
from pipeline.export import publish_paths
from pipeline.layout import Box, collisions


def check_voice(day: Path) -> tuple[bool, str]:
    meta = json.loads((day / "tts_sentences.json").read_text(encoding="utf-8"))
    if meta.get("voice") != VOICE_ID or meta.get("provider") != "edge-tts":
        return False, f"file voice={meta.get('voice')!r} provider={meta.get('provider')!r}"
    bad = [s["text"][:40] for s in meta["sentences"] if s.get("voice") != VOICE_ID]
    if bad:
        return False, f"segments with the wrong voice: {bad[:3]}"
    return True, VOICE_ID


def check_caption_contract(day: Path) -> tuple[bool, str]:
    align = json.loads((day / "align.json").read_text(encoding="utf-8"))
    if align.get("clock") != "edge-tts-word-boundary":
        return False, f"clock is {align.get('clock')!r}, not the TTS word boundary"
    problems = []
    for group in align["captions"]:
        words = group.get("words") or []
        rebuilt = " ".join(w["text"] for w in words)
        if rebuilt != group["text"]:
            problems.append(f"text {group['text']!r} != {' '.join(w['text'] for w in words)!r}")
        if len(words) > 1 and " " not in group["text"]:
            problems.append(f"missing space in {group['text']!r}")
        if words and group["end_frame"] < words[-1]["end_frame"]:
            problems.append(
                f"{group['text']!r} ends at {group['end_frame']} before word end "
                f"{words[-1]['end_frame']}"
            )
        if group["end_frame"] <= group["frame"]:
            problems.append(f"non-positive duration for {group['text']!r}")
    if problems:
        return False, "; ".join(problems[:4])
    return True, f"{len(align['captions'])} groups keep spaces and word ends"


def check_publish_name(day: Path) -> tuple[bool, str]:
    final, _music = publish_paths(day)
    if not final.exists():
        return False, f"missing {final.name}"
    if "sample-final" in final.name:
        return False, final.name
    return True, final.name


def check_layout_example() -> tuple[bool, str]:
    """The shared rule itself: a loose caption must not sit on a headline."""
    boxes = [
        Box("headline", 200, 360, 680, 140, "headline"),
        Box("caption", 180, 1460, 720, 90, "caption"),
        Box("probe-label", 400, 700, 120, 40, "label", label_of="probe"),
        Box("probe", 380, 680, 160, 80, "illustration"),
    ]
    bad = collisions(boxes)
    if bad:
        return False, str(bad)
    clash = collisions([
        Box("headline", 200, 360, 680, 140, "headline"),
        Box("caption", 200, 400, 400, 80, "caption"),
    ])
    if not clash:
        return False, "overlap of headline and caption was not detected"
    return True, "label-on-node allowed; unrelated overlap detected"
