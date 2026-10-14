#!/usr/bin/env python3
"""
A Bit Inside - the single source of truth for time (section 7.1).

Everything downstream reads this file: the renderer, the audio engine and the QA
gates. Every event is a named frame number at 30 fps. Scene lengths come from the
TTS durations that were actually measured, never from an estimate.

Writes timeline.json and re-writes script.md so its timestamps are real.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DAY = HERE.parent
sys.path.insert(0, str(HERE))

FPS = 30
ENDCARD_FRAMES = 36            # 1.2 s, under the 1.5 s cap
HEADLINE_IN = 12               # slide-up + fade, ease-out cubic
HEADLINE_OUT = 8
PAYOFF_MIN_HOLD_FRAMES = 45    # 1.5 s
MIN_TICK_GAP = 12              # one meaningful sound every ~0.4 s at most
WHOOSH_LEAD = 8                # whoosh starts this many frames before a cut
RISER_LEAD = 60                # 2 s riser before the reveal
REVEAL_SILENCE = 12            # 0.4 s designed drop after the riser

# Scenes that carry a designed sound moment.
IMPACT_SCENES = {"hook", "the_reveal"}
CHIME_SCENES = {"payoff", "question"}
RISER_BEFORE = "the_reveal"


def f(t_seconds: float) -> int:
    return int(round(t_seconds * FPS))


def beat_frame(scene: dict, k: int) -> int:
    """Must match render/scenes.py::beat_frame exactly, or the label-pop click
    drifts away from the visual beat it belongs to. Beat 0 is the scene's first
    frame, so every scene has something on screen from the cut."""
    n = len(scene.get("beats", []))
    if n <= 0:
        return scene["start_frame"]
    a, b = scene["start_frame"], scene["end_frame"]
    return a + int((b - a) * k / n)


def main() -> int:
    plan = json.loads((DAY / "scenes_plan.json").read_text(encoding="utf-8"))
    tts = json.loads((DAY / "tts_sentences.json").read_text(encoding="utf-8"))
    align = json.loads((DAY / "align.json").read_text(encoding="utf-8"))

    # group sentences by scene, in order
    by_scene: dict[str, list[dict]] = {}
    for s in tts["sentences"]:
        by_scene.setdefault(s["scene"], []).append(s)

    caps_by_scene: dict[str, list[dict]] = {}
    for c in align["captions"]:
        caps_by_scene.setdefault(c["scene"], []).append(c)

    # ------------------------------------------------ scene frame ranges
    starts: dict[str, int] = {}
    for s in plan["scenes"]:
        ss = by_scene.get(s["id"], [])
        if ss:
            starts[s["id"]] = f(ss[0]["start_seconds"])
        elif s["id"] == "endcard":
            starts[s["id"]] = None            # filled in below
    # the end card starts after the last narration plus its trailing gap
    last_end_s = tts["sentences"][-1]["start_seconds"] + tts["sentences"][-1]["seconds"]
    trailing_gap = tts["sentences"][-1]["gap_after_seconds"]
    starts["endcard"] = f(last_end_s + trailing_gap)

    ids = [s["id"] for s in plan["scenes"]]
    # The first scene owns frame 0 even when the narration has a lead-in: the hook
    # claim and its headline must be on screen from the very first frame.
    starts[ids[0]] = 0
    ranges: dict[str, tuple[int, int]] = {}
    for i, sid in enumerate(ids):
        start = starts[sid]
        if sid == "endcard":
            end = start + ENDCARD_FRAMES
        else:
            nxt = next((starts[ids[j]] for j in range(i + 1, len(ids))
                        if starts[ids[j]] is not None), None)
            end = nxt if nxt is not None else f(last_end_s + trailing_gap)
        ranges[sid] = (start, end)

    total = ranges["endcard"][1]
    if total < f(65):
        raise SystemExit(f"timeline is only {total / FPS:.1f} s, below the 65 s hard gate")

    # ------------------------------------------------ narration inside each scene
    def sent_frames(sid: str, ss: list[dict]) -> list[dict]:
        out = []
        for s in ss:
            out.append({
                "text": s["text"],
                "start_frame": f(s["start_seconds"]),
                "end_frame": f(s["start_seconds"] + s["seconds"]),
                "lufs_before": s["lufs_before"],
            })
        return out

    # ------------------------------------------------ captions
    for sid, caps in caps_by_scene.items():
        for c in caps:
            a, b = ranges[sid]
            c["frame"] = max(a, min(c["frame"], b - 1))

    # ------------------------------------------------ sound events
    events: list[dict] = []

    def add(name: str, frame: int, kind: str, gain_db: float, note: str = "") -> None:
        events.append({"name": name, "frame": max(0, frame), "kind": kind,
                       "gain_db": gain_db, "note": note})

    for i, sid in enumerate(ids):
        a, b = ranges[sid]
        if i > 0 and sid != "endcard":
            add(f"whoosh_into_{sid}", max(0, a - WHOOSH_LEAD), "whoosh", -9.0,
                f"scene cut into {sid}")

    # word-card ticks on caption groups, thinned to meaningful beats
    last_tick = -999
    for sid in ids:
        for c in caps_by_scene.get(sid, []):
            if c["frame"] - last_tick < MIN_TICK_GAP:
                continue
            last_tick = c["frame"]
            add(f"tick_{sid}_{c['frame']}", c["frame"], "tick",
                -12.0, f"caption group '{c['text']}'")

    # label pops: one per beat, placed across the scene
    for s in plan["scenes"]:
        sid = s["id"]
        a, b = ranges[sid]
        for k in range(len(s.get("beats", []))):
            sc = {"start_frame": a, "end_frame": b, "beats": s.get("beats", [])}
            at = beat_frame(sc, k)
            add(f"pop_{sid}_{k}", at, "click", -11.0, s["beats"][k][:52])

    # counter ticks: the numbers that count up
    for sid, label in (("the_flaw", "severity meter fills to 8.2"),
                       ("the_scale", "2,765 controllers light up"),
                       ("the_reveal", "case temperature flips to 50")):
        a, b = ranges[sid]
        for k in range(5):
            at = a + int((b - a) * (0.35 + 0.11 * k))
            add(f"counter_{sid}_{k}", at, "tick_rise", -15.0, label)

    # typing, random intervals, inside the code-of-the-day scene
    a, b = ranges["the_flaw"]
    for k, frac in enumerate((0.30, 0.345, 0.40, 0.44, 0.475, 0.515, 0.55, 0.585)):
        add(f"typing_{k}", a + int((b - a) * frac), "typing", -20.0,
            "code of the day types itself out")

    # riser + designed silence before the reveal
    ra, rb = ranges[RISER_BEFORE]
    add("riser_before_reveal", max(0, ra - RISER_LEAD), "riser", -13.0,
        "ascending tension into the reveal")
    add("reveal_silence_drop", ra - REVEAL_SILENCE, "silence", 0.0,
        "200-400 ms designed cut to silence before the reveal")
    add("impact_reveal", ra, "impact", -3.0, "sub-drop + thump on the reveal")

    # impact on the hook, and the sonic-logo chime
    for sid in IMPACT_SCENES:
        add(f"impact_{sid}", ranges[sid][0], "impact", -5.0, f"key beat in {sid}")
    for sid in CHIME_SCENES:
        b = ranges[sid][1]
        add(f"chime_{sid}", max(ranges[sid][0], b - 40), "chime", -6.0,
            "two-note chime, resolves to a major chord")

    # low buzz under the myth/wrong beat in the gap scene
    ga, gb = ranges["the_gap"]
    add("buzz_gap", ga + 6, "buzz", -17.0, "no one has named the flaw")

    # reverse whoosh into the loop frame
    add("reverse_whoosh_loop", max(0, ranges["endcard"][0] - 10), "whoosh_rev", -10.0,
        "reverse whoosh into the loop frame")

    # ------------------------------------------------ assemble
    scenes_out = []
    for s in plan["scenes"]:
        sid = s["id"]
        a, b = ranges[sid]
        sc = {
            "id": sid,
            "index": len(scenes_out),
            "start_frame": a,
            "end_frame": b,
            "duration_frames": b - a,
            "headline": s["headline"],
            "headline_in_frame": a,
            "headline_out_frame": max(a, b - HEADLINE_OUT),
            "illustration": s["illustration"],
            "beats": s.get("beats", []),
            "sentences": sent_frames(sid, by_scene.get(sid, [])),
            "captions": caps_by_scene.get(sid, []),
        }
        if s["id"] == "endcard":
            sc["loop"] = True
            sc["render_as"] = "hook"
            sc["render_frame"] = 0
        scenes_out.append(sc)

    payoff = next(s for s in scenes_out if s["id"] == "payoff")
    payoff_hold = payoff["end_frame"] - payoff["sentences"][-1]["start_frame"]
    if payoff_hold < PAYOFF_MIN_HOLD_FRAMES:
        shortfall = PAYOFF_MIN_HOLD_FRAMES - payoff_hold
        # push the next scene and everything after it out by the shortfall
        idx = scenes_out.index(payoff)
        for later in scenes_out[idx + 1:]:
            for key in ("start_frame", "end_frame", "headline_in_frame",
                        "headline_out_frame"):
                later[key] += shortfall
            for e in events:
                if e["frame"] > payoff["end_frame"]:
                    e["frame"] += shortfall
        total += shortfall
        scenes_out[idx]["end_frame"] += shortfall
        scenes_out[idx]["duration_frames"] += shortfall
        payoff_hold += shortfall

    out = {
        "fps": FPS,
        "total_frames": total,
        "duration_seconds": round(total / FPS, 3),
        "narration_seconds": tts["narration_seconds"],
        "length_scale": tts["length_scale"],
        "voice": tts["voice"],
        "endcard_frames": ENDCARD_FRAMES,
        "endcard_seconds": ENDCARD_FRAMES / FPS,
        "payoff_hold_frames": payoff_hold,
        "payoff_hold_seconds": round(payoff_hold / FPS, 2),
        "scene_count": len(scenes_out),
        "scenes": scenes_out,
        "events": sorted(events, key=lambda e: (e["frame"], e["name"])),
        "rules": {
            "headline_in_frames": HEADLINE_IN,
            "headline_out_frames": HEADLINE_OUT,
            "whoosh_lead_frames": WHOOSH_LEAD,
            "min_tick_gap_frames": MIN_TICK_GAP,
            "riser_lead_frames": RISER_LEAD,
            "reveal_silence_frames": REVEAL_SILENCE,
        },
    }
    (DAY / "timeline.json").write_text(json.dumps(out, indent=1, ensure_ascii=False),
                                       encoding="utf-8")

    print(f"timeline: {total} frames = {total / FPS:.2f} s at {FPS} fps")
    for s in scenes_out:
        print(f"  f{s['start_frame']:>5}-{s['end_frame']:<5} "
              f"({s['duration_frames'] / FPS:5.2f}s)  {s['id']:<12} "
              f"{s['headline']}")
    print(f"payoff hold {out['payoff_hold_seconds']} s, end card {out['endcard_seconds']} s")
    print(f"sound events: {len(out['events'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())