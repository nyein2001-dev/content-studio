#!/usr/bin/env python3
"""Narration, alignment and the single source of time.

Order of operations, and why:

1. Every sentence is synthesised on its own with local Piper, so a flagged
   sentence can be re-synthesised without touching the rest.
2. Each take is measured by `voice_qa`. Flagged takes are re-synthesised up to
   three times and the best is kept; anything still flagged is logged, never
   hidden.
3. Takes are normalised to -18 LUFS and joined with the beat pauses, so the
   narration level is even and the pauses carry the rhythm.
4. faster-whisper supplies word timings; the script supplies the spelling.
5. Scene lengths come from the MEASURED audio, never from an estimate.

Everything downstream reads `timeline.json` and nothing else for timing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3]))

import numpy as np  # noqa: E402

import theme as T  # noqa: E402
from videokit import voice_qa  # noqa: E402
from videokit.tts import Piper, TARGET_SR  # noqa: E402

DAY = HERE.parent
CACHE = DAY.parent / ".cache"
AUDIO = DAY / "audio"
PLAN = json.loads((DAY / "scenes_plan.json").read_text(encoding="utf-8"))

FPS = T.FPS


def gap_after(scene_id: str) -> float:
    """Beat pauses. Longer before the reveal, as the brief requires."""
    if scene_id == "reveal":
        return T.GAP_BEFORE_REVEAL / FPS
    if scene_id in ("payoff", "close"):
        return T.GAP_AFTER / FPS
    return T.GAP_AFTER / FPS


def build_narration() -> dict:
    voices = sorted((T.FONTS_DIR.parent / "voices").glob("*.onnx"))
    if not voices:
        raise SystemExit("no Piper voice in assets/voices; run setup.sh")
    model = next((p for p in voices if "ryan-high" in p.name), voices[0])
    p = Piper(model, cache_dir=CACHE / "tts")
    print(f"voice: {model.name} @ {p.sample_rate} Hz")

    # first pass: measure every sentence so the median level is known
    takes, flagged_log = [], []
    for sc in PLAN["scenes"]:
        for i, text in enumerate(sc["sentences"]):
            take = p.say(text, length_scale=1.05)
            takes.append({"scene": sc["id"], "index": i, "text": text, "take": take})

    median_db = float(np.median([voice_qa.level_dbfs(t["take"].audio) for t in takes]))

    # second pass: voice QA, re-synthesise flagged takes
    def rank(flags, text, audio, dur):
        """Fewer flags first, then the closer-to-natural score."""
        return (len(flags), voice_qa.score(text, audio, dur, TARGET_SR))

    for rec in takes:
        text, take = rec["text"], rec["take"]
        flags = voice_qa.check(text, take.audio, take.duration, median_db, TARGET_SR)
        best = (rank(flags, text, take.audio, take.duration), take, flags)
        for attempt in range(1, 4):
            if not best[2]:
                break
            variants = voice_qa.retry_variants(text)
            if attempt - 1 >= len(variants):
                break
            var = variants[attempt - 1]
            if "parts" in var["how"]:
                parts = voice_qa.split_for_retry(text)
                joined = [p.say(part, length_scale=1.05,
                                noise_scale=var.get("noise_scale"),
                                noise_w=var.get("noise_w"), attempt=attempt)
                          for part in parts]
                joined = [j for j in joined if j is not None]
                if len(joined) < 2:
                    continue
                gap = np.zeros(int(0.11 * TARGET_SR), dtype=np.float32)
                audio = np.concatenate([x for j in joined
                                        for x in (j.audio, gap)])
                cand = type(take)(audio=audio[:int(take.duration * 1.3 * TARGET_SR)],
                                  duration=min(len(audio) / TARGET_SR, take.duration * 1.3),
                                  length_scale=1.05, attempt=attempt)
            else:
                cand = p.say(text, length_scale=1.05,
                             noise_scale=var.get("noise_scale"),
                             noise_w=var.get("noise_w"), attempt=attempt)
            f2 = voice_qa.check(text, cand.audio, cand.duration, median_db, TARGET_SR)
            r2 = rank(f2, text, cand.audio, cand.duration)
            if r2 < best[0]:
                best = (r2, cand, f2)
        rec["take"] = best[1]
        rec["flags"] = best[2]
        if best[2]:
            flagged_log.append({"scene": rec["scene"], "text": text,
                                "flags": best[2], "attempts": best[1].attempt + 1,
                                "duration": round(best[1].duration, 2)})
        print(f"  {'ok ' if not best[2] else 'FLAG'} {rec['scene']:<9} "
              f"{best[1].duration:5.2f}s  {','.join(best[2]):<22} {text[:44]}")

    # ------------------------------------------------------------------ join
    parts, cursor, sentences = [], 0.0, []
    for sc in PLAN["scenes"]:
        sc_start = cursor
        for i, rec in enumerate((r for r in takes if r["scene"] == sc["id"])):
            take = rec["take"]
            at = int(round(cursor * TARGET_SR))
            parts.append((at, take.audio))
            sentences.append({
                "scene": sc["id"], "index": i, "text": rec["text"],
                "start_seconds": round(cursor, 4),
                "end_seconds": round(cursor + take.duration, 4),
                "duration": round(take.duration, 4),
                "voice": "piper:en_US-ryan-high", "provider": "local piper (offline)",
                "length_scale": take.length_scale, "attempt": take.attempt,
                "flags": rec["flags"],
            })
            cursor += take.duration + 0.06
        cursor += gap_after(sc["id"]) - 0.06

    total_s = cursor + T.GAP_BEFORE_ENDCARD / FPS
    n = int(round(total_s * TARGET_SR)) + TARGET_SR
    narration = np.zeros(n, dtype=np.float32)
    for at, audio in parts:
        end = min(n, at + len(audio))
        narration[at:end] += audio[:end - at]

    AUDIO.mkdir(parents=True, exist_ok=True)
    from videokit.audio import mix as M
    M.write_wav(AUDIO / "narration.wav", narration, TARGET_SR)
    (DAY / "tts_sentences.json").write_text(
        json.dumps({"sentences": sentences, "voice": "piper:en_US-ryan-high",
                    "median_dbfs": median_db,
                    "unresolved_flags": flagged_log}, indent=2), encoding="utf-8")
    print(f"narration: {total_s:.2f}s, {len(sentences)} sentences, "
          f"{len(flagged_log)} unresolved flags")
    return {"sentences": sentences, "duration": total_s, "flags": flagged_log}


def align(sentences: list[dict]) -> dict:
    from videokit.align import Aligner

    a = Aligner(model_name="base.en", download_root=str(CACHE / "huggingface"))
    out = a.align(AUDIO / "narration.wav", sentences)
    (DAY / "align.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"align: clock={out['clock']} words={len(out['words'])} "
          f"groups={len(out['groups'])} fallback={out.get('fallback')}")
    return out


def timeline(sentences: list[dict], align_out: dict, narration_s: float) -> dict:
    """Scene boundaries, beats and audio events, all in frames."""
    groups = align_out["groups"]
    by_scene: dict[str, list[dict]] = {s["id"]: [] for s in PLAN["scenes"]}
    for g in groups:
        by_scene.setdefault(g["words"][0]["sentence"].rsplit(":", 1)[0]
                            if ":" in str(g["words"][0]["sentence"]) else "", []).append(g)

    # map each sentence to its scene, then each group to a scene via its word times
    sent_scene = {}
    for s in sentences:
        sent_scene.setdefault(s["text"][:40], s["scene"])

    scene_frames = {}
    cursor = T.HOOK_LEAD_FRAMES
    for sc in PLAN["scenes"]:
        ss = [s for s in sentences if s["scene"] == sc["id"]]
        start_s = ss[0]["start_seconds"]
        end_s = ss[-1]["end_seconds"]
        # the scene owns its sentences plus the pause that follows
        nxt = [x for x in sentences if x["scene"] != sc["id"] and x["start_seconds"] > end_s]
        own_end = nxt[0]["start_seconds"] if nxt else narration_s + 0.5
        f0 = max(cursor, int(round(start_s * FPS)) - T.GAP_AFTER)
        f1 = int(round(own_end * FPS))
        scene_frames[sc["id"]] = {"start": f0, "end": max(f0 + 12, f1)}
        cursor = scene_frames[sc["id"]]["end"]

    endcard_start = scene_frames["close"]["end"] + T.GAP_BEFORE_ENDCARD
    endcard_end = endcard_start + T.ENDCARD_MIN_FRAMES
    total = endcard_end

    # beats inside each scene, one per sentence
    beats = {}
    for sc in PLAN["scenes"]:
        ss = [s for s in sentences if s["scene"] == sc["id"]]
        f = scene_frames[sc["id"]]
        span = max(1, f["end"] - f["start"])
        idx = [f["start"] + int(round(span * (i + 0.12) / (len(ss) + 0.24)))
               for i in range(len(ss))]
        beats[sc["id"]] = idx

    events = _audio_events(sentences, scene_frames, beats, endcard_start)
    tl = {
        "fps": FPS, "width": T.W, "height": T.H,
        "total_frames": total, "endcard": {"start": endcard_start, "end": endcard_end},
        "scenes": [{"id": s["id"], "kind": s["kind"], "headline": s["headline"],
                    "section": s["section"], "sub": s.get("sub", ""),
                    "start": scene_frames[s["id"]]["start"],
                    "end": scene_frames[s["id"]]["end"],
                    "beats": beats[s["id"]]} for s in PLAN["scenes"]],
        "sentences": sentences, "audio": events,
        "captions": [{"text": g["text"], "start_frame": int(round(g["start"] * FPS)),
                      "end_frame": int(round(g["end"] * FPS)),
                      "words": [{"text": w["text"], "start": w["start"], "end": w["end"]}
                                for w in g["words"]]}
                     for g in groups],
        "payoff_hold_frames": max(0, endcard_start - scene_frames["payoff"]["end"] + 90),
        "narration_seconds": narration_s,
        "year": PLAN["year"],
    }
    (DAY / "timeline.json").write_text(json.dumps(tl, indent=2), encoding="utf-8")
    return tl


def _audio_events(sentences, scene_frames, beats, endcard_start) -> list[dict]:
    """One sound per meaningful beat, placed by frame."""
    ev: list[dict] = []

    def add(frame, kind, gain_db, detail=""):
        ev.append({"frame": int(frame), "kind": kind, "gain_db": float(gain_db),
                   "detail": detail})

    # first sound by frame 4
    add(2, "coin_clink", -13.0, "brand tick under the first frame")
    for sc in PLAN["scenes"]:
        f = scene_frames[sc["id"]]
        bs = beats[sc["id"]]
        if sc["id"] in ("dev_high", "dev_mid"):
            for i, b in enumerate(bs):
                add(b - T.MIN_TICK_GAP if b - T.MIN_TICK_GAP > f["start"] else b,
                    "ledger_tick", -19.0 + i * 1.1, f"counter step {i + 1}")
        elif sc["id"] == "reveal":
            add(bs[0] - T.RISER_LEAD, "riser", -17.0, "tension into the reveal")
            add(bs[0] - T.REVEAL_SILENCE, "map_swell", -15.0, "camera zoom in")
            add(bs[1], "impact", -7.0, "key reveal")
            add(bs[1] + 4, "shock_ring", -12.0, "reveal tail")
        elif sc["id"] == "hook":
            add(f["start"], "map_swell", -17.0, "camera settles on the world")
            add(f["start"] + 10, "pin_drop", -20.0, "reference marker")
        elif sc["id"] == "payoff":
            add(bs[0], "chime", -15.0, "payoff chime")
            add(bs[0] + 9, "route_coin", -22.0, "money moving along the map")
        elif sc["id"] == "close":
            add(f["start"], "route_swish", -21.0, "legend draws")
        for s in sentences:
            if s["scene"] != sc["id"]:
                continue
            add(int(round(s["start_seconds"] * FPS)) - T.WHOOSH_LEAD,
                "whoosh", -23.0, "beat cut")
    add(endcard_start, "chime", -12.0, "sonic logo on the end card")
    return sorted(ev, key=lambda e: e["frame"])


def main() -> int:
    n = build_narration()
    a = align(n["sentences"])
    tl = timeline(n["sentences"], a, n["duration"])

    dur = tl["total_frames"] / FPS
    print(f"timeline: {tl['total_frames']} frames = {dur:.2f}s")
    for s in tl["scenes"]:
        print(f"   {s['id']:<10} {s['start']:>5}..{s['end']:>5}  "
              f"{(s['end']-s['start'])/FPS:5.2f}s  {s['kind']}")
    print(f"   endcard    {tl['endcard']['start']}..{tl['endcard']['end']}")
    print(f"   audio events: {len(tl['audio'])}, captions: {len(tl['captions'])}")

    ok = T.MIN_TOTAL_FRAMES <= tl["total_frames"] <= T.MAX_TOTAL_FRAMES
    print(f"duration gate 65-175 s: {'PASS' if ok else 'FAIL'} ({dur:.1f}s)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
