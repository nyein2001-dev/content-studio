"""Load layout_spec.yaml. Every layout number enters through here."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT
ABIT = ROOT.parent
SPEC_PATH = PACKAGE / "layout_spec.yaml"
SCHEMA_PATH = PACKAGE / "schema" / "layout_spec.schema.json"


class SpecError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def load_spec() -> dict:
    if not SPEC_PATH.is_file():
        raise SpecError(f"missing layout spec at {SPEC_PATH}")
    raw = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(raw), key=lambda e: list(e.path))
    if errors:
        detail = "; ".join(f"{'/'.join(map(str, e.path))}: {e.message}" for e in errors[:8])
        raise SpecError(f"layout_spec.yaml failed schema validation: {detail}")
    _require_zones(raw)
    _require_type_floors(raw)
    return raw


def _require_zones(spec: dict) -> None:
    needed = {
        "PLATFORM_TOP", "BRAND", "TITLE", "BADGE", "STAGE",
        "SUBTITLE", "PLATFORM_BOTTOM",
    }
    missing = needed - set(spec["zones"])
    if missing:
        raise SpecError(f"layout spec is missing zones: {sorted(missing)}")
    if spec["default_profile"] not in spec["profiles"]:
        raise SpecError("default_profile is not defined")


def _require_type_floors(spec: dict) -> None:
    for name, role in spec["type"].items():
        if role["floor"] > role["preferred"]:
            raise SpecError(f"type {name} floor is above its preferred size")
        if role["floor"] % spec["spacing"]["shrink_step"] and role["preferred"] != role["floor"]:
            # Floors may be odd; the ladder still stops on the floor.
            pass


def token(spec: dict, group: str, name: str):
    try:
        return spec[group][name]
    except KeyError as exc:
        raise SpecError(f"layout spec has no {group}.{name}") from exc
