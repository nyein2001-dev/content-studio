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
            f"{scene}: R15: duration {doc['duration_s']}s is under "
            f"{rules['min_scene_duration_s']}s. Fix: lengthen the narration or merge this beat with the next one."
        )
    stage = doc.get("stage") or []
    if len(stage) > int(rules["max_stage_components"]):
        problems.append(
            f"{scene}: R15: {len(stage)} stage components exceeds {rules['max_stage_components']}. "
            "Fix: split this scene in the DSL."
        )
    chips = chip_count(doc)
    if chips > int(rules["max_chips"]):
        problems.append(
            f"{scene}: R15: {chips} chips exceeds {rules['max_chips']}. Fix: split the chip row across two scenes."
        )
    if doc.get("overlay") and int(rules["max_overlays"]) < 1:
        problems.append(f"{scene}: R15: overlays are not allowed. Fix: remove the cursor.")
    overlays = 1 if doc.get("overlay") else 0
    if overlays > int(rules["max_overlays"]):
        problems.append(
            f"{scene}: R15: {overlays} overlays exceeds {rules['max_overlays']}. Fix: keep a single cursor."
        )
    blocks = text_block_count(doc)
    if blocks > int(rules["max_extra_text_blocks"]):
        problems.append(
            f"{scene}: R15: {blocks} text blocks besides the headline and caption exceeds "
            f"{rules['max_extra_text_blocks']}. Fix: split the scene."
        )
    zone = zones_for(doc.get("profile")).rect("TITLE")
    pad = spec["spacing"]["text_pad_x"]
    try:
        fitted = fit_text(scene, doc["headline"], "title", zone.w - 2 * pad, allow_shrink=True)
    except LayoutError as exc:
        problems.append(
            f"{scene}: R15: title does not fit in two lines at the title size. Fix: {exc.remedy}"
        )
        fitted = None
    if fitted is not None:
        limit = int(rules["title_chars_per_line"])
        for line in fitted.lines:
            if len(line) > limit:
                problems.append(
                    f"{scene}: R15: title line {line!r} is {len(line)} chars and the limit is {limit}."
                )
    words = len(str(doc.get("caption") or "").split())
    if words > int(rules["subtitle_words"]):
        problems.append(
            f"{scene}: R15: subtitle has {words} words and the limit is {rules['subtitle_words']}."
        )
    chip_limit = int(rules["chip_chars"])
    head_limit = int(rules["card_heading_chars"])
    sub_limit = int(rules["card_sub_chars"])
    for comp in doc.get("stage") or []:
        for label in comp.get("labels") or []:
            if len(label) > chip_limit:
                problems.append(f"{scene}: R15: chip label {label!r} exceeds {chip_limit} chars.")
        for spoke in comp.get("spokes") or []:
            if len(spoke.get("label") or "") > chip_limit:
                problems.append(
                    f"{scene}: R15: chip label {spoke.get('label')!r} exceeds {chip_limit} chars."
                )
        title = comp.get("title") or ""
        if title and len(title) > head_limit and comp["type"] in ("card", "callout", "hub_and_spoke"):
            problems.append(f"{scene}: R15: card heading {title!r} exceeds {head_limit} chars.")
        body = comp.get("body") or ""
        if body and len(body) > sub_limit:
            problems.append(f"{scene}: R15: card sub-line {body!r} exceeds {sub_limit} chars.")
    return problems
