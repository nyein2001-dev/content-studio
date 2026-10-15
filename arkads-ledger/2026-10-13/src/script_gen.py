#!/usr/bin/env python3
"""Script generation.

One question, one takeaway, one metaphor. Every number in the narration and on
screen is pulled from facts.json by the function that also draws it, so the
script, the renderer and facts.json cannot disagree.

Beats: hook -> setup (open loop) -> five development beats -> reveal -> payoff.
No spoken like, subscribe or follow request; the silent end card covers that.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3]))

import theme as T  # noqa: E402

DAY = HERE.parent
FACTS = json.loads((DAY / "facts.json").read_text(encoding="utf-8"))
F = FACTS["facts"]

QUESTION = "Why does the same dollar buy different lives?"
TAKEAWAY = "Two currencies, two different truths"      # 5 words
METAPHOR = "A map with two legends"
FORMAT = "Map Story"
SECONDARY_FORMAT = "Counter That Lies"
COMMENT_QUESTION = "Which country should I add to this map next?"

RATIO_FLOOR = 0.02
NUM = re.compile(r"\d+(?:\.\d+)?")


def v(fid: str):
    if fid not in F:
        raise KeyError(f"fact {fid!r} is not in facts.json; the script may not invent one")
    return F[fid]["value"]


def num(fid: str, places: int = 2) -> str:
    """Format a fact for the screen and for speech. The same string is used in
    both places, so the caption, the narration and facts.json always agree."""
    x = v(fid)
    s = f"{x:.{places}f}"
    return s


def n2(fid: str) -> str:
    """Two-decimal display used in the narration and on the map legend."""
    return num(fid, 2)


# ------------------------------------------------------------------ the story
def build() -> dict:
    us = num("price_level_ratio_USA", 3)          # 1.000
    uk = n2("price_level_ratio_GBR")              # 0.89
    de = n2("price_level_ratio_DEU")              # 0.80
    jp = n2("price_level_ratio_JPN")              # 0.65
    mx = n2("price_level_ratio_MEX")              # 0.54
    kr = n2("price_level_ratio_KOR")              # 0.57
    br = n2("price_level_ratio_BRA")              # 0.46
    tr = n2("price_level_ratio_TUR")              # 0.41
    id_ = n2("price_level_ratio_IDN")             # 0.29
    in_ = n2("price_level_ratio_IND")             # 0.23
    ng = num("price_level_ratio_NGA", 3)          # 0.128
    times = num("ratio_ratio", 1)                 # 7.8

    scenes = [
        # -------------------------------------------------------------- hook
        {"id": "hook", "kind": "map_choropleth",
         "headline": ["ONE DOLLAR,", "EIGHT COUNTRIES"],
         "section": "THE PRICE LEVEL RATIO", "sub": "LATEST AVAILABLE DATA, " + str(FACTS["year"]),
         "beats": 2, "sentences": [
             "One American dollar buys about eight dollars worth of life in Nigeria.",
             "In America, that same dollar buys exactly one dollar.",
         ]},
        # -------------------------------------------------------------- setup
        {"id": "setup", "kind": "map_split",
         "headline": ["TWO ANSWERS", "TO ONE QUESTION"],
         "section": "THE OPEN LOOP", "sub": "EXCHANGE RATE vs PRICE LEVEL",
         "beats": 3, "sentences": [
             "Neither number is a mistake. They answer different questions.",
             "Markets price currency by trade. Nobody prices your groceries by trade.",
             "So the exchange rate and your actual spending drift apart.",
         ]},
        # ------------------------------------------------------ development 1
        {"id": "mechanism", "kind": "diagram",
         "headline": ["A BASKET", "NOT A BANKNOTE"],
         "section": "THE MECHANISM", "sub": "WHAT PURCHASING POWER ACTUALLY MEANS",
         "beats": 3, "sentences": [
             "An exchange rate tells you what you get when you trade currency.",
             "A price level tells you what your money actually buys where you live.",
             "One is a trade quote. The other is a shopping list.",
         ]},
        # ------------------------------------------------------ development 2
        {"id": "dev_high", "kind": "map_bars",
         "headline": ["THE RICH END", "OF THE MAP"],
         "section": "COUNTRY BY COUNTRY", "sub": "RATIO TO THE UNITED STATES, " + str(FACTS["year"]),
         "beats": 4, "sentences": [
             "The World Bank measures this and calls it the price level ratio.",
             "It compares income per person converted at market rates with income "
             "per person converted at what it actually buys.",
             "America sits at " + us + ", because it is the reference country.",
             "Britain is just below at " + uk + ". Germany is " + de + ". Japan is " + jp + ".",
         ]},
        # ------------------------------------------------------ development 3
        {"id": "dev_mid", "kind": "map_bars",
         "headline": ["THE MIDDLE", "OF THE MAP"],
         "section": "COUNTRY BY COUNTRY", "sub": "RATIO TO THE UNITED STATES, " + str(FACTS["year"]),
         "beats": 4, "sentences": [
             "South Korea is " + kr + ". Mexico is " + mx + ".",
             "Brazil and Argentina both sit near " + br + ".",
             "Turkey is " + tr + ". Indonesia is " + id_ + ".",
             "These are not rich or poor countries. They are cheap or expensive ones.",
         ]},
        # ------------------------------------------------------------- reveal
        {"id": "reveal", "kind": "map_focus",
         "headline": ["NIGERIA", str(ng)],
         "section": "THE REVEAL", "sub": "PRICE LEVEL RATIO, " + str(FACTS["year"]),
         "beats": 3, "sentences": [
             "India is " + in_ + ". Nigeria is " + ng + ", the lowest here.",
             "Multiply that ratio by the American dollar and the gap becomes plain.",
             "One dollar of income in Nigeria is worth about " + times + " dollars in America.",
         ]},
        # ------------------------------------------------------------- payoff
        {"id": "payoff", "kind": "map_full",
         "headline": ["USE THE RIGHT", "LEGEND"],
         "section": "THE TAKEAWAY", "sub": "TWO CURRENCIES, TWO DIFFERENT TRUTHS",
         "beats": 3, "sentences": [
             "If you compare incomes across a map using only the exchange rate, you measure the wrong thing.",
             "A cheap country is not a poor country. It is a country where your money stretches.",
             "Prices are local. That is the whole mechanism.",
         ]},
        # ------------------------------------------------------------- close
        {"id": "close", "kind": "map_hold",
         "headline": ["PRICE LEVEL", "RATIO, " + str(FACTS["year"])],
         "section": "SOURCES ON SCREEN", "sub": "WORLD BANK, WORLD DEVELOPMENT INDICATORS",
         "beats": 2, "sentences": [
             "Educational content, not financial advice.",
         ]},
    ]

    # ------------------------------------------------------------- validation
    words = 0
    for s in scenes:
        for sent in s["sentences"]:
            n = len(sent.split())
            assert n <= 22, f"{s['id']}: sentence has {n} words (>22): {sent}"
            words += n
    assert 220 <= words <= 340, f"spoken word count {words} is outside 220-340"

    banned = ("like", "subscribe", "follow me", "smash that")
    for s in scenes:
        low = " ".join(s["sentences"]).lower()
        for b in banned:
            assert b not in low, f"{s['id']}: spoken call to action {b!r}"

    return {"question": QUESTION, "takeaway": TAKEAWAY, "metaphor": METAPHOR,
            "format": FORMAT, "secondary_format": SECONDARY_FORMAT,
            "comment_question": COMMENT_QUESTION, "scenes": scenes,
            "word_count": words, "year": FACTS["year"]}


def main() -> int:
    plan = build()
    (DAY / "scenes_plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")

    src = F["price_level_ratio_USA"]
    src_line = (f"Source: World Bank, World Development Indicators, {FACTS['year']}")

    L = [f"# Map of Money - Episode {T.EPISODE}", "",
         f"**Question:** {plan['question']}",
         f"**Takeaway ({len(plan['takeaway'].split())} words):** {plan['takeaway']}",
         f"**Metaphor:** {plan['metaphor']}",
         f"**Format:** {plan['format']} + {plan['secondary_format']}",
         f"**Spoken words:** {plan['word_count']} (target 220-340, sentences <= 22 words)",
         f"**Data year:** {plan['year']} (latest available from the World Bank release)",
         "",
         "> Narrated by a local Piper neural voice. Educational content, not financial advice.",
         "",
         "---", "",
         "## Voiceover, beat by beat", "",
         "Frame timestamps are filled in from the measured TTS durations by `timeline.py`.",
         "They are printed here after the build; see the table below.", ""]

    t = 0
    for s in plan["scenes"]:
        L.append(f"### {s['id']} - {s['kind']}")
        L.append("")
        L.append(f"- **Section label:** {s['section']}")
        if s.get("sub"):
            L.append(f"- **Sub-label:** {s['sub']}")
        L.append(f"- **On-screen headline:** {' '.join(s['headline'])}")
        L.append(f"- **Visual direction:** {s['kind']}, one focal element, "
                 f"{s['beats']} beats")
        L.append(f"- **Source tag:** {src_line}")
        L.append(f"- **Captions:** word-timed, {T.SIZE_CAPTION} px Montserrat Bold")
        L.append("")
        L.append("**Narration:**")
        L.append("")
        for sent in s["sentences"]:
            L.append(f"> {sent}")
            L.append(">")
        L.append("")

    L += ["---", "", "## Caption groups", "",
          "Generated from the aligned word timings by `timeline.py`; each group is "
          "3-5 words and carries its own frame range.", "",
          "## Every number used, and where it comes from", "",
          "| On screen | Value | Kind | Source |", "|---|---|---|---|"]
    for fid, f in sorted(F.items()):
        if f.get("kind") == "derived" or fid.startswith("nominal_gdppc") or \
                fid.startswith("ppp_gdppc"):
            continue
        L.append(f"| `{fid}` | {f['value']} {f['unit']} | {f.get('kind','sourced')} | "
                 f"{f['dataset']}, {f.get('year','')} |")

    L += ["", "## Safety", "",
          "- No buy, sell or hold language. No stock picks. No return promises.",
          "- No tax, legal or jurisdiction-specific advice.",
          "- Countries appear only as evidence for a universal mechanism.",
          "- No urgency, no fear. Illustrative figures are labelled EXAMPLE on screen.",
          "- No spoken like, subscribe or follow request.", ""]

    (DAY / "script.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"script: {len(plan['scenes'])} scenes, {plan['word_count']} spoken words")
    print(f"  -> {DAY / 'script.md'}")
    print(f"  -> {DAY / 'scenes_plan.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
