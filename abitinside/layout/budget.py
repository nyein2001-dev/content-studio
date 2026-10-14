"""Density budget. Runs before any pixels are drawn."""
from __future__ import annotations

from layout.errors import LayoutError
from layout.fit import fit_text
from layout.spec import load_spec
from layout.zones import zones_for


def text_block_count(doc: dict) -> int:
    count = 0
    for comp in doc.get("stage") or []:
        kind = comp["type"]
        if comp.get("title"):
            count += 1
        if comp.get("body"):
            count += 1
        if comp.get("value"):
            count += 1
        if comp.get("score_label"):
            count += 1
        if kind == "checklist":
            count += len(comp.get("items") or [])
        if kind == "flow":
            count += len(comp.get("steps") or [])
        if kind == "comparison":
            for side in ("left", "right"):
                block = comp.get(side) or {}
                if block.get("title"):
                    count += 1
                if block.get("body"):
                    count += 1
        if kind == "code_panel":
            count += 1
        if kind in ("flow", "hub_and_spoke", "timeline"):
            # Titles already counted. Step and tick labels are axis or chip labels.
            pass
    return count


def chip_count(doc: dict) -> int:
    total = 0
    for comp in doc.get("stage") or []:
        if comp["type"] == "chip_row":
            total += len(comp.get("labels") or [])
        if comp["type"] == "hub_and_spoke":
            total += len(comp.get("spokes") or [])
    return total


def check_budget(doc: dict) -> list[str]:
    """Return human remedies. Empty means the scene is inside the budget."""
    spec = load_spec()
    rules = spec["rules"]
    problems = []
    scene = doc["id"]
    if float(doc["duration_s"]) < float(rules["min_scene_duration_s"]):
        problems.append(
            f"{scene}: LR-13: duration {doc['duration_s']}s is under "
            f"{rules['min_scene_duration_s']}s. Fix: lengthen the narration or merge this beat with the next one."
        )
    stage = doc.get("stage") or []
    if len(stage) > int(rules["max_stage_components"]):
        problems.append(
            f"{scene}: LR-13: {len(stage)} stage components exceeds {rules['max_stage_components']}. "
            "Fix: split this scene in the DSL."
        )
    chips = chip_count(doc)
    if chips > int(rules["max_chips"]):
        problems.append(
            f"{scene}: LR-13: {chips} chips exceeds {rules['max_chips']}. Fix: split the chip row across two scenes."
        )
    if doc.get("overlay") and int(rules["max_overlays"]) < 1:
        problems.append(f"{scene}: LR-13: overlays are not allowed. Fix: remove the cursor.")
    overlays = 1 if doc.get("overlay") else 0
    if overlays > int(rules["max_overlays"]):
        problems.append(
            f"{scene}: LR-13: {overlays} overlays exceeds {rules['max_overlays']}. Fix: keep a single cursor."
        )
    blocks = text_block_count(doc)
    if blocks > int(rules["max_extra_text_blocks"]):
        problems.append(
            f"{scene}: LR-13: {blocks} text blocks besides the headline and caption exceeds "
            f"{rules['max_extra_text_blocks']}. Fix: split the scene."
        )
    zone = zones_for(doc.get("profile")).rect("HEADLINE")
    pad = spec["spacing"]["text_pad_x"]
    try:
        fit_text(scene, doc["headline"], "headline", zone.w - 2 * pad, allow_shrink=False)
    except LayoutError as exc:
        problems.append(
            f"{scene}: LR-13: headline does not fit in two lines at the headline size. Fix: {exc.remedy}"
        )
    return problems
