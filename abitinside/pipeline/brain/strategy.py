"""Read the channel strategy file. Topics have to sit inside it."""
from __future__ import annotations

from pipeline.config import CONTENT_IDEA

CORE_MARKERS = (
    "how the internet works",
    "smartphones",
    "apps",
    "algorithms",
    "cloud computing",
    "search engines",
    "recommendation systems",
    "batteries",
    "chips",
    "encryption",
    "digital payments",
    "data centers",
    "operating systems",
    "online platforms",
    "gps",
)


def load_text() -> str:
    if not CONTENT_IDEA.exists():
        raise SystemExit(f"content strategy file is missing: {CONTENT_IDEA}")
    return CONTENT_IDEA.read_text(encoding="utf-8", errors="replace")


def core_topics() -> list[str]:
    text = load_text().lower()
    found = [topic for topic in CORE_MARKERS if topic in text]
    if len(found) < 8:
        raise SystemExit("the content strategy file does not contain the channel topic list")
    return found


def fits_channel(blob: str) -> bool:
    low = blob.lower()
    return any(topic in low for topic in core_topics()) or "inside" in low
