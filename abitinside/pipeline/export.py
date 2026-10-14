"""Publish filenames come from the title, not from a temporary sample name."""
from __future__ import annotations

import json
import re
from pathlib import Path


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    if not slug or slug in {"video", "sample", "sample-final", "output", "final"}:
        raise SystemExit(f"refusing a meaningless filename for title {title!r}")
    return slug[:80].strip("-")


def publish_paths(day: Path) -> tuple[Path, Path]:
    meta_path = day / "youtube-metadata.json"
    if not meta_path.exists():
        raise SystemExit(f"no title metadata at {meta_path}")
    title = json.loads(meta_path.read_text(encoding="utf-8"))["title"]
    slug = slugify(title)
    video = day / "video"
    return video / f"{slug}.mp4", video / f"{slug}-music-sfx.mp4"


def remember(day: Path, final: Path, music: Path) -> None:
    meta_path = day / "youtube-metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["file"] = f"video/{final.name}"
    meta["alternate_file"] = f"video/{music.name}"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
