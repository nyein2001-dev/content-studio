"""Reject a topic that repeats a title, question, or mechanism already published."""
from __future__ import annotations

import json
import re
from pathlib import Path

HISTORY = Path(__file__).resolve().parent / "history.json"


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def load() -> list[dict]:
    if not HISTORY.exists():
        return []
    return json.loads(HISTORY.read_text(encoding="utf-8"))["entries"]


def duplicate_reason(candidate: dict, day: str) -> str | None:
    title = _norm(candidate.get("title", ""))
    question = _norm(candidate.get("question", ""))
    mechanism = _norm(candidate.get("mechanism") or candidate.get("id", ""))
    blob = " ".join(part for part in (title, question, mechanism) if part)
    for entry in load():
        if entry.get("day") == day:
            continue
        for field in ("title", "question", "mechanism"):
            previous = _norm(entry.get(field, ""))
            if len(previous) < 8:
                continue
            if previous in blob or (title and title in previous):
                return (
                    f"repeats {field} {entry.get(field)!r} "
                    f"already used on {entry.get('day')}"
                )
    return None


def assert_not_duplicate(candidate: dict, day: str) -> None:
    reason = duplicate_reason(candidate, day)
    if reason:
        raise SystemExit(f"duplicate topic rejected: {reason}")
