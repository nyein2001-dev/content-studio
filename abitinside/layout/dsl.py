"""Scene DSL loader. Coordinates and font sizes are rejected by the schema."""
from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from layout.errors import LayoutError
from layout.spec import PACKAGE

SCHEMA = json.loads((PACKAGE / "schema" / "scene.schema.json").read_text(encoding="utf-8"))
_VALIDATOR = Draft202012Validator(SCHEMA)


def load_scene(path: Path | str) -> dict:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise LayoutError(
            path.stem, "LR-13",
            "scene file is not a mapping",
            "Write a scene DSL document. Do not put coordinates in this file.",
        )
    errors = sorted(_VALIDATOR.iter_errors(data), key=lambda item: list(item.path))
    if errors:
        detail = "; ".join(
            f"{'/'.join(map(str, err.path)) or '<root>'}: {err.message}" for err in errors[:6]
        )
        raise LayoutError(
            str(data.get("id") or path.stem), "LR-13",
            f"scene DSL is invalid: {detail}",
            "Match prompts/layout_contract.md. Remove coordinates, font sizes, and unknown fields.",
        )
    data.setdefault("splittable", False)
    data.setdefault("footnote", "")
    data.setdefault("connectors", [])
    data.setdefault("overlay", None)
    data.setdefault("profile", "portrait")
    _reject_coordinates(data, str(data.get("id") or path.stem))
    return data


def _reject_coordinates(data, scene: str) -> None:
    banned = {"x", "y", "w", "h", "font_size", "size", "color", "colour", "hex"}

    def walk(node) -> None:
        if isinstance(node, dict):
            found = banned & set(node)
            if found:
                raise LayoutError(
                    scene, "LR-13",
                    f"scene DSL contains layout fields {sorted(found)}",
                    "Delete coordinates, sizes, and colours. The solver places the scene and the theme supplies colour.",
                )
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)


def load_video(path: Path | str) -> dict:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "scenes" not in data:
        raise LayoutError(path.stem, "LR-13", "video file needs a scenes list", "List scene DSL paths under scenes.")
    base = path.parent
    scenes = []
    for item in data["scenes"]:
        scenes.append(load_scene(base / item))
    data["scene_docs"] = scenes
    return data
