#!/usr/bin/env python3
"""
A Bit Inside - the script (section 5).

One question, one takeaway of six words, one visual metaphor, 240-330 spoken
words, sentences no longer than 22 words, no spoken like/follow.

The scene list below is the single editorial source. It produces:
  * scenes_plan.json  - scene id, headline lines, sentences, illustration key,
                        beats, caption highlight words. Read by timeline.py.
  * script.md         - the human-readable script with timestamps. Timestamps are
                        read back from timeline.json once the TTS durations are
                        measured, so nothing in script.md is an estimate.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DAY = HERE.parent

QUESTION = "How did attackers get to a supermarket fridge?"
TAKEAWAY = "The fridge was never really offline."          # 6 words
METAPHOR = "the cold-chain trace"
FORMAT = "Data story / Two Lines"

# The one spoken question, also used verbatim as the pinned comment.
COMMENT_QUESTION = "So: is anything in your home reachable from the internet?"

# ---------------------------------------------------------------- the script
SCENES = [
    {
        "id": "hook",
        "headline": ["FIFTY DEGREAS", "IN ONE NIGHT"],
        "sentences": [
            "Attackers drove supermarket fridges in France to fifty degrees, overnight.",
        ],
        "illustration": "trace_crash",
        "beats": [
            "Cold-chain trace slams upward from the healthy band and pins at 50 C",
            "Store cross-section flashes once behind it, then drops back",
        ],
        "cyan": [],
    },
    {
        "id": "setup",
        "headline": ["150 STORES", "WOKE UP WARM"],
        "sentences": [
            "About a hundred and fifty of those stores woke up to warm cases and food in the bin.",
            "Nobody had broken into a fridge.",
            "Someone had loaded a web page.",
        ],
        "illustration": "store_elevation",
        "beats": [
            "Store elevation appears: cases, one glowing controller box on the back wall",
            "A 150-dot waffle of stores fills, one dot per store, on the word 'stores'",
            "The web page card loads on top of the fridge, then covers the fridge",
        ],
        "cyan": ["stores"],
    },
    {
        "id": "controller",
        "headline": ["ONE BOX", "BEHIND THE CASES"],
        "sentences": [
            "Behind the cases sits one small box that runs them all.",
            "It reads the temperature probes, holds the target, and schedules the defrost cycle.",
        ],
        "illustration": "controller_cutaway",
        "beats": [
            "Camera pushes into the back wall, the box grows to fill the frame",
            "Three labelled taps grow out of it: PROBES, TARGET, DEFROST",
            "Thin signal lines run from the box to three chilled cases",
        ],
        "cyan": ["box"],
    },
    {
        "id": "why_online",
        "headline": ["A WEB PAGE", "IN THE STORE"],
        "sentences": [
            "It has a web interface, because the engineer who installed it has to clear alarms at night.",
            "Driving to the shop for every alarm was the problem they were solving.",
        ],
        "illustration": "engineer_path",
        "beats": [
            "A router ring pulses at the bottom, a line climbs to the box",
            "A LATE-NIGHT pill pops, an alarm card pulses on the store floor",
            "The engineer's van stops travelling; the line stays lit",
        ],
        "cyan": ["web interface"],
    },
    {
        "id": "the_flaw",
        "headline": ["A PASSWORD", "MADE OF DATES"],
        "sentences": [
            "Security researchers found three flaws in that interface.",
            "One was a hidden login, generated from the controller's own date.",
            "Anyone who could reach the page could work out that day's code.",
            "It scored 8.2 out of 10 for severity.",
        ],
        "illustration": "code_of_day",
        "beats": [
            "THREE FLAWS card, three numbered slots fill",
            "A calendar page flips to today's date and a code types itself out",
            "The generated code slides into an empty login box",
            "SEVERITY meter fills to 8.2 with a HIGH tag",
        ],
        "cyan": ["login"],
    },
    {
        "id": "the_scale",
        "headline": ["2,765 CONTROLLERS", "ON THE INTERNET"],
        "sentences": [
            "Scanning for exposed controllers, the researchers counted two thousand seven hundred and sixty-five.",
            "Sitting on the public internet.",
            "Nobody knows how many were ever patched.",
        ],
        "illustration": "exposed_grid",
        "beats": [
            "A 40 x 20 grid of tiny controller glyphs fades in",
            "2,765 of them light cyan as the counter rolls",
            "A PATCHED? chip stays grey and unreadable",
        ],
        "cyan": ["controllers"],
    },
    {
        "id": "legacy",
        "headline": ["MOST WERE", "ALREADY UNSUPPORTED"],
        "sentences": [
            "The manufacturer says most of the boxes that were hit were older models it no longer updates.",
            "The AK-SM 800 stopped getting security fixes in 2021.",
            "The AK-SC 355 was phased out in 2016.",
        ],
        "illustration": "support_timeline",
        "beats": [
            "A firmware timeline draws from AUG 2025 to OCT 2026",
            "AK-SM 800 card greys out at 2021",
            "AK-SC 355 card greys out at 2016",
        ],
        "cyan": [],
    },
    {
        "id": "defrost",
        "headline": ["DEFROST, FOREVER"],
        "sentences": [
            "A freezer has to run a defrost cycle, or ice builds up on the coil.",
            "That cycle is a normal, scheduled job.",
            "Reporting says the attackers simply turned it on and never let it stop.",
        ],
        "illustration": "defrost_cycle",
        "beats": [
            "A coil cross-section grows icicles, then a heater bar glows",
            "DEFROST pill pulses on a clock ring",
            "The clock ring loses its stop mark; the heater bar stays lit",
        ],
        "cyan": ["defrost"],
    },
    {
        "id": "the_reveal",
        "headline": ["BY MORNING,", "FIFTY DEGREES"],
        "sentences": [
            "By morning, the cases were at fifty degrees.",
            "France's CERT published an alert the next day, naming the controller series.",
            "A Paris prosecutor opened an inquiry.",
        ],
        "illustration": "morning_scene",
        "beats": [
            "The trace peaks at 50 C and a CASE TEMP card flips to 50",
            "CERTFR-2026-ALE-012 card slides in, AK-SM and AK-SC chips tick",
            "COPELAND XWEB and DIXELL XWEB chips tick too, then the alert card dims",
            "A gavel-free inquiry card stamps: INQUIRY OPENED",
        ],
        "cyan": ["CERT"],
    },
    {
        "id": "the_gap",
        "headline": ["NO CVE.", "NO NAMES."],
        "sentences": [
            "Still, no one has named the flaw that was used, or how they got in.",
            "The CERT's advice is blunt: take the box off the internet.",
        ],
        "illustration": "unknown_then_advice",
        "beats": [
            "Three question cards stack: WHO, HOW, WHICH FLAW, each unanswered",
            "They are swept off screen by a TAKE IT OFF THE INTERNET card",
            "The store's connection line is cut with a drawn X",
        ],
        "cyan": [],
    },
    {
        "id": "payoff",
        "headline": ["THE FRIDGE WAS", "NEVER OFFLINE"],
        "sentences": [
            "A refrigeration controller is not something anyone chose to put online.",
            "It just answers a web page, wherever it is plugged in.",
            "The fridge was never really offline.",
        ],
        "illustration": "loop_trace",
        "beats": [
            "The cold-chain trace rewinds to its start, cool and flat",
            "The store elevation returns, exactly as frame one",
            "The trace holds flat for the closing beat",
        ],
        "cyan": ["web page"],
    },
    {
        "id": "question",
        "headline": ["YOUR TURN"],
        "sentences": [
            COMMENT_QUESTION,
        ],
        "illustration": "home_network",
        "beats": [
            "The trace flattens into a calm band",
            "A simple house outline draws in, four device dots inside it",
            "One dot pulses amber and a question mark sits above it",
        ],
        "cyan": [],
    },
    {
        "id": "endcard",
        # The end card is the loop frame: the same composition as frame 1, so the
        # Short cuts back to the start seamlessly. The wordmark is the only
        # follow prompt, and it is already on screen from frame 1.
        "headline": ["FIFTY DEGREAS", "IN ONE NIGHT"],
        "sentences": [],
        "illustration": "loop_frame",
        "beats": [
            "Holds the frame 1 composition; the impact ring keeps expanding",
        ],
        "cyan": [],
    },
]

# ---------------------------------------------------------------- helpers
def spoken_words() -> list[str]:
    out = []
    for s in SCENES:
        for line in s["sentences"]:
            out.extend(line.split())
    return out


def sentences() -> list[tuple[str, str]]:
    return [(s["id"], line) for s in SCENES for line in s["sentences"]]


def validate() -> list[str]:
    problems = []
    words = spoken_words()
    n = len(words)
    if not (240 <= n <= 330):
        problems.append(f"spoken word count {n} is outside 240-330")
    if len(TAKEAWAY.split()) > 6:
        problems.append("takeaway is longer than six words")
    banned = re.compile(r"\b(like|like this|like that|subscribe|follow me|hey guys|welcome|"
                        r"did you know|smash that|comment below)\b", re.I)
    for _, line in sentences():
        w = len(line.split())
        if w > 22:
            problems.append(f"sentence over 22 words ({w}): {line}")
        if banned.search(line):
            problems.append(f"banned phrase in: {line}")
        if not line[0].isupper():
            problems.append(f"sentence does not start uppercase: {line}")
    for s in SCENES:
        if len(s["headline"]) > 2:
            problems.append(f"{s['id']}: headline has more than two lines")
        total = sum(len(l.split()) for l in s["headline"])
        if total > 8:
            problems.append(f"{s['id']}: headline has {total} words (max 8)")
        for line in s["headline"]:
            if len(line.split()) > 4:
                problems.append(f"{s['id']}: headline line over 4 words: {line}")
            if line != line.upper():
                problems.append(f"{s['id']}: headline not uppercase: {line}")
    if not SCENES or "hook" not in SCENES[0]["id"]:
        problems.append("first scene is not the hook")
    if not any(s["sentences"] and COMMENT_QUESTION in s["sentences"][-1] for s in SCENES):
        problems.append("comment question is not spoken by the last narrated scene")
    return problems


# ---------------------------------------------------------------- emit
def write_plan() -> None:
    plan = {
        "question": QUESTION,
        "takeaway": TAKEAWAY,
        "metaphor": METAPHOR,
        "format": FORMAT,
        "comment_question": COMMENT_QUESTION,
        "word_count": len(spoken_words()),
        "scenes": SCENES,
    }
    (DAY / "scenes_plan.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False),
                                          encoding="utf-8")


def fmt(t: float) -> str:
    m, s = divmod(t, 60)
    return f"{int(m)}:{s:04.1f}"


def write_script_md() -> None:
    tl_path = DAY / "timeline.json"
    tl = json.loads(tl_path.read_text(encoding="utf-8")) if tl_path.exists() else None
    L: list[str] = []
    a = L.append
    a(f"# A Bit Inside - 2026-10-13")
    a("")
    a(f"**Question:** {QUESTION}")
    a("")
    a(f"**Takeaway:** {TAKEAWAY}")
    a("")
    a(f"**Visual metaphor:** {METAPHOR}  |  **Format:** {FORMAT}")
    a("")
    n = len(spoken_words())
    a(f"**Spoken words:** {n}  (target 240-330)")
    a("")
    if tl:
        a(f"**Runtime:** {fmt(tl['total_frames'] / tl['fps'])} s "
          f"({tl['total_frames']} frames at {tl['fps']} fps), measured from real TTS durations")
        a("")
        a("Narration is Piper `en_US-ryan-high`, synthesised sentence by sentence. Every "
          "timestamp below is derived from the measured length of the audio, never estimated.")
    else:
        a("**Runtime:** not yet measured (run `tts.py` then re-run this file)")
    a("")
    a("---")
    a("")
    a("## Full voiceover, scene by scene")
    a("")
    for i, s in enumerate(SCENES):
        t0 = t1 = None
        if tl:
            sc = tl["scenes"][i]
            t0, t1 = sc["start_frame"] / tl["fps"], sc["end_frame"] / tl["fps"]
        span = f"`{fmt(t0)} - {fmt(t1)}`" if t0 is not None else "`pending`"
        a(f"### {i:02d}. {span}  **{s['id']}**")
        a("")
        a(f"- **On-screen headline:** {' / '.join(f'`{h}`' for h in s['headline'])}")
        a(f"- **Illustration:** `{s['illustration']}`")
        if s["sentences"]:
            a("")
            for line in s["sentences"]:
                a(f"> {line}")
        else:
            a("")
            a("> *(no speech - the visual end card carries the follow prompt)*")
        if s["beats"]:
            a("")
            a("- **Beats:**")
            for b in s["beats"]:
                a(f"  - {b}")
        if tl and i < len(tl["scenes"]):
            caps = tl["scenes"][i].get("captions", [])
            if caps:
                a("")
                a("- **Caption groups** (frame = first frame the word is spoken):")
                for c in caps:
                    mark = "cyan" if c.get("accent") == "cyan" else (
                        "yellow" if c.get("accent") == "yellow" else "plain")
                    a(f"  - f{c['frame']:>5} `{c['text']}`  ({mark})")
        a("")
    a("---")
    a("")
    a("## Closing comment question")
    a("")
    a(f"> {COMMENT_QUESTION}")
    a("")
    a("This is the pinned comment, verbatim. The video never asks for likes, follows or "
      "subscriptions out loud; the end card carries any follow prompt visually.")
    a("")
    a("## Numbers used, and where each one comes from")
    a("")
    facts = json.loads((DAY / "facts.json").read_text(encoding="utf-8"))["facts"]
    byid = {f["id"]: f for f in facts}
    for f in facts:
        if not f.get("used_on_screen"):
            continue
        src = f.get("source_url", "")
        kind = f.get("kind", "?")
        extra = ""
        if f.get("derivation"):
            extra = f" - derived: {f['derivation']}"
        if f.get("explained"):
            extra += f" - **{'illustrative/simplified' if f.get('kind') == 'illustrative' else 'simplified'}**"
        a(f"- **{f['label']}** = `{f['value']}` {f['unit']} ({kind}){extra}")
        a(f"  - {src}")
    a("")
    (DAY / "script.md").write_text("\n".join(L), encoding="utf-8")


def main() -> int:
    problems = validate()
    write_plan()
    write_script_md()
    print(f"spoken words: {len(spoken_words())}")
    print(f"sentences:    {len(sentences())}")
    print(f"scenes:       {len(SCENES)}")
    if problems:
        print("\nSCRIPT PROBLEMS:")
        for p in problems:
            print("  -", p)
        return 1
    print("validation: OK")
    print("wrote scenes_plan.json and script.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())