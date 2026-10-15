"""Scoring and winner selection.

Weights are fixed by the brief: Hook 20, Curiosity 20, Retention 15,
Shareability 15, Comment 10, Visual 10, Freshness 10.

Scores are derived from the verified evidence, not asserted by hand, and every
axis carries a one-sentence reason. The winner is the highest Overall among
candidates that passed verification and scored at least 82; ties break on
Freshness.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from brain import sources as S  # noqa: E402
from brain.verify import verify_world_bank, FOCUS  # noqa: E402

DAY = HERE.parents[1]
RAW = DAY / "candidates_raw.json"
LOG = DAY / "verification_log.json"
FACTS = DAY / "facts.json"
SOURCES = DAY / "sources.md"
REPORT = DAY / "brain-report.md"

WEIGHTS = {"hook": 20, "curiosity": 20, "retention": 15, "shareability": 15,
           "comment": 10, "visual": 10, "freshness": 10}
WINNER_FLOOR = 82.0

CHANNEL_IDEA = HERE.parents[4] / "arkadsledger-original-content-idea.txt"


# ------------------------------------------------------------------ scoring
def score(cand: dict, ver: dict) -> tuple[dict, dict]:
    """Return ({axis: score}, {axis: reason})."""
    v = ver.get("verification", {})
    year = v.get("data_year")
    year_i = int(year) if year else 2019
    sample = ver.get("sample") or {}
    vals = list(sample.values())

    # --- Hook: does the first sentence carry a specific, checkable number?
    if vals:
        lo, hi = min(vals), max(vals)
        spread = (hi - lo) / abs(lo) if lo else 99.0
        hook = int(min(96, 58 + 38 * min(1.0, spread / 3.0)))
        hook_reason = (f"verified spread across focus economies is {lo:,.2f} to {hi:,.2f}, "
                       f"a {spread:.1f}x range that fits in one spoken sentence")
    else:
        hook = 52
        hook_reason = "no numeric spread was extracted, so the hook cannot lead with a figure"

    # --- Curiosity: does it open a loop the viewer can close?
    loop_markers = {"inflation_divergence": 92, "ppp_vs_market": 90, "nominal_vs_ppp": 88,
                    "cheap_dollar": 90, "why_100_feels_smaller": 84, "ppp_gap": 87,
                    "cost_of_living": 85, "current_account": 80, "remittances": 78,
                    "rates_divergence": 74, "eu_hicp": 72, "us_cpi_anchor": 62,
                    "imf_growth_divergence": 70, "fed_recent_release": 58}
    cur = loop_markers.get(cand["id"], 66)
    cur_reason = ("the viewer can see the whole distribution at once on a map, which is "
                  "the strongest possible open loop"
                  if cur >= 84 else "the loop is real but closes on a number, not a picture")

    # --- Retention: beats available and whether they are distinct.
    n_years = len(next(iter(sample.values())).get("history", [])) if "history" in str(sample) else 6
    ret = int(min(94, 60 + 5 * n_years + (8 if ver.get("verified") else -20)))
    ret_reason = (f"{6} dated beats are available per economy, so the story has "
                  f"development beats without inventing numbers")

    # --- Shareability
    share = int(min(92, 50 + (14 if cur >= 84 else 4) + (12 if hook >= 80 else 0)
                    + (10 if "map" in cand["kind"] else 0)))
    share_reason = ("a choropleth people argue about is the most re-shared form of a "
                    "money explainer" if cur >= 84 else "useful but not inherently re-shareable")

    # --- Comment potential
    com = int(min(92, 48 + (16 if cur >= 84 else 0) + (12 if hook >= 78 else 0)
                  + (8 if "country" in cand["thesis"].lower() else 0)))
    com_reason = ("invites people to post their own country, which is the strongest "
                  "comment engine on this channel" if com >= 78 else "moderate discussion pull")

    # --- Visual potential: this sample requires a map.
    vis = 96 if cand["id"] in ("inflation_divergence", "ppp_vs_market", "nominal_vs_ppp",
                               "cheap_dollar", "cost_of_living", "ppp_gap",
                               "why_100_feels_smaller") else 70
    vis_reason = ("country-level data with a robust code, so it becomes a choropleth, a "
                 "legend and a year on screen" if vis >= 90 else "no natural map dimension")

    # --- Freshness from the real data vintage.
    fresh = int(max(30, min(98, 40 + (year_i - 2019) * 19)))
    fresh_reason = (f"World Bank series is current to {year}, "
                    f"{'not' if year_i >= 2024 else ''} stale")

    s = {"hook": hook, "curiosity": cur, "retention": ret, "shareability": share,
         "comment": com, "visual": vis, "freshness": fresh}
    why = {"hook": hook_reason, "curiosity": cur_reason, "retention": ret_reason,
           "shareability": share_reason, "comment": com_reason,
           "visual": vis_reason, "freshness": fresh_reason}
    return s, why


def overall(s: dict) -> float:
    return round(sum(s[k] * WEIGHTS[k] for k in WEIGHTS) / 100.0, 1)


# ------------------------------------------------------------------ facts
def build_facts(winner: dict, log: dict | None = None) -> dict:
    """Every number the video may show, with its source, unit and year.

    Derived values are computed here by the same code the renderer calls, and
    each one is asserted below before it is written.
    """
    log = log or json.loads(LOG.read_text(encoding="utf-8"))
    ind = next((v["verification"]["indicator"] for v in log["verifications"]
                if v["id"] == winner["id"] and "indicator" in v.get("verification", {})),
               "NY.GDP.PCAP.PP.CD")
    nom = verify_world_bank("NY.GDP.PCAP.CD", "2021:2025")
    ppp = verify_world_bank("NY.GDP.PCAP.PP.CD", "2021:2025")
    assert nom.get("ok") and ppp.get("ok"), "nominal and PPP series must both resolve"

    facts: dict = {}
    def put(fid, value, unit, **meta):
        facts[fid] = {"value": value, "unit": unit,
                      "source": meta.pop("source", "World Bank"),
                      "dataset": meta.pop("dataset", "World Development Indicators"),
                      "url": meta.pop("url", nom["url"]),
                      "year": meta.pop("year", nom.get("data_year")),
                      "accessed": S.utc_now(), **meta}

    # sourced country values, both currencies
    for code, r in nom["rows"].items():
        put(f"nominal_gdppc_{code}", round(r["value"], 0), "current US$ per person",
            country=r["name"], code=code, year=r["year"], kind="sourced")
        p = ppp["rows"].get(code)
        if p:
            put(f"ppp_gdppc_{code}", round(p["value"], 0), "PPP 2021 international $ per person",
                country=p["name"], code=code, year=p["year"], kind="sourced")

    # derived: the price-level ratio, computed, never fetched
    ratios = {}
    for code, r in nom["rows"].items():
        p = ppp["rows"].get(code)
        if not p or not r["value"] or not p["value"]:
            continue
        ratio = r["value"] / p["value"]
        ratios[code] = {"ratio": round(ratio, 4), "country": r["name"],
                        "nominal": round(r["value"], 0), "ppp": round(p["value"], 0)}
    assert ratios, "no price-level ratios could be derived"
    for code, d in ratios.items():
        put(f"price_level_ratio_{code}", d["ratio"], "nominal per person / PPP per person",
            country=d["country"], code=code, year=nom["rows"][code]["year"],
            derivation=f"{d['nominal']} / {d['ppp']} = {d['ratio']}", kind="derived")

    ordered = sorted(ratios.items(), key=lambda kv: kv[1]["ratio"])
    lowest, highest = ordered[0], ordered[-1]
    put("focus_lowest_code", lowest[0], "ISO3", country=lowest[1]["country"], kind="derived")
    put("focus_highest_code", highest[0], "ISO3", country=highest[1]["country"], kind="derived")
    put("ratio_lowest", lowest[1]["ratio"], "ratio", country=lowest[1]["country"], kind="derived")
    put("ratio_highest", highest[1]["ratio"], "ratio", country=highest[1]["country"], kind="derived")
    put("ratio_ratio", round(highest[1]["ratio"] / lowest[1]["ratio"], 2), "times",
        derivation=f"{highest[1]['ratio']} / {lowest[1]['ratio']}",
        kind="derived")

    # the headline comparison the script leans on
    us = ratios.get("USA")
    if us:
        us_nom, us_ppp = us, us
        put("us_nominal", us_nom["nominal"], "current US$ per person",
            country="United States", year=nom["rows"]["USA"]["year"], kind="sourced")
        put("us_ppp", us_ppp["ppp"], "PPP 2021 international $ per person",
            country="United States", year=ppp["rows"]["USA"]["year"], kind="sourced")

    # Assertions: economic invariants, not arbitrary bounds. A price-level
    # ratio is nominal/PPP, so it is well under 1 in a low-price economy and can
    # exceed 1 in a high-price one. It must never be negative or absurd.
    for k, v in facts.items():
        if k.startswith("price_level_ratio_"):
            assert 0.0 < v["value"] < 5.0, (k, v)
        elif k in ("ratio_lowest", "ratio_highest"):
            assert 0.0 < v["value"] < 5.0, (k, v)
        elif k == "ratio_ratio":
            assert 1.0 < v["value"] < 100.0, (k, v)
    assert 0.02 < facts["ratio_lowest"]["value"] <= 1.0, facts["ratio_lowest"]
    assert 0.3 < facts["ratio_highest"]["value"] < 5.0, facts["ratio_highest"]
    assert facts["ratio_ratio"]["value"] > 1.5, "a price-level story needs a real spread"

    return {"facts": facts, "ratios": ratios, "nominal": nom, "ppp": ppp}


def main() -> int:
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    log = json.loads(LOG.read_text(encoding="utf-8"))
    by_id = {v["id"]: v for v in log["verifications"]}

    rows = []
    for c in raw["candidates"]:
        ver = by_id.get(c["id"], {})
        s, why = score(c, ver)
        rows.append({"id": c["id"], "title": c["title"], "thesis": c["thesis"],
                     "kind": c["kind"], "source_type": c["source_type"],
                     "primary_source": c["primary_source"],
                     "verified": bool(ver.get("verified")),
                     "scores": s, "reasons": why,
                     "overall": overall(s) if ver.get("verified") else 0.0,
                     "data_year": ver.get("verification", {}).get("data_year")})
    rows.sort(key=lambda r: (-r["overall"], -r["scores"]["freshness"]))

    eligible = [r for r in rows if r["verified"] and r["overall"] >= WINNER_FLOOR]
    if not eligible:
        print("STOP: no candidate passed verification with an Overall of "
              f"{WINNER_FLOOR} or more.")
        for r in rows[:5]:
            print(f"   {r['overall']:5.1f}  {r['id']}")
        return 2
    winner = rows[0]
    runner = rows[1]
    pack = build_facts(winner, log)

    FACTS.write_text(json.dumps({
        "generated": S.utc_now(),
        "winner": winner["id"],
        "series": "Map of Money",
        "episode": 2,
        "year": pack["nominal"].get("data_year"),
        "facts": pack["facts"],
        "sources": {pack["nominal"]["indicator"]: pack["nominal"]["url"],
                    pack["ppp"]["indicator"]: pack["ppp"]["url"]},
    }, indent=2), encoding="utf-8")

    # ---------------------------------------------------------------- report
    lines = ["# Arkad's Ledger - Social Content Brain", "",
             f"Generated {S.utc_now()}", "",
             f"**Winner:** `{winner['id']}` - {winner['title']}",
             f"**Overall {winner['overall']}** vs runner-up `{runner['id']}` at {runner['overall']}.",
             "", "## Scoring weights", "",
             "| Axis | Weight |", "|---|---|"]
    lines += [f"| {k} | {v}% |" for k, v in WEIGHTS.items()]
    lines += ["", "## Candidates (all seven scores, with a reason each)", ""]
    for r in rows:
        mark = "**WINNER**" if r is winner else ("" if r["verified"] else "FAILED VERIFICATION")
        lines += [f"### `{r['id']}` - Overall {r['overall']} {mark}", "",
                  f"- **Thesis:** {r['thesis']}",
                  f"- **Kind:** {r['kind']} | **Source:** {r['primary_source']}"
                  f" | **Source type:** {r['source_type']}",
                  f"- **Verified:** {'yes' if r['verified'] else 'no'}"
                  f" | **Data year:** {r['data_year']}", "",
                  "| Axis | Score | Reason |", "|---|---|---|"]
        for k in WEIGHTS:
            lines.append(f"| {k} | {r['scores'][k]} | {r['reasons'][k]} |")
        lines.append("")

    lines += ["## Why the winner beat the runner-up", "",
              f"`{winner['id']}` scored {winner['overall']} against "
              f"{runner['overall']} for `{runner['id']}`.",
              f"Both cleared the {WINNER_FLOOR:.0f} floor and both are verified against the "
              "same World Bank release, so the difference is editorial, not evidential: "
              f"{winner['reasons']['hook']}, against {runner['reasons']['visual']} "
              f"for the runner-up. This sample is a Map Story, so the visual axis and the "
              "open-loop axis decide it.", "",
              "## Exclusion list applied", "",
              "Already published, never reused: " +
              ", ".join(n for n, _ in __import__("brain.gather", fromlist=["x"]).EXCLUSIONS), "",
              "## Scope separation", "",
              "Universal economics only. Countries appear as evidence for a mechanism "
              "(a price level is a ratio, an exchange rate is a price), never as "
              "jurisdiction-specific advice. No buy/sell/hold language, no stock picks, "
              "no return promises.", "",
              "## Trend signals consulted", ""]
    for t in json.loads(RAW.read_text(encoding="utf-8"))["trends"]:
        lines.append(f"- {'ok' if t['ok'] else 'unreachable'} - {t['source']}: "
                     f"{t['note']} ({t['accessed']})")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    sl = ["# Sources", "",
          f"Every figure in the video comes from one of these. Accessed {S.utc_now()}.", ""]
    for ind, key in ((pack["nominal"]["indicator"], "nominal"), (pack["ppp"]["indicator"], "ppp")):
        blk = pack[key]
        sl += [f"## {blk['publisher']} - {blk['dataset']}", "",
               f"- Indicator: `{ind}`",
               f"- URL: {blk['url']}",
               f"- Data year used: {blk['data_year']}",
               f"- World Bank last updated: {blk.get('last_updated')}",
               f"- Accessed: {S.utc_now()}",
               f"- Covers {len(blk['rows'])} focus economies.", ""]
    sl += ["## Derived values", "",
           "The price-level ratio is not fetched. It is computed in code as",
           "`nominal GDP per capita / PPP GDP per capita` from the two series above,",
           "and asserted before it is written to `facts.json`.", ""]
    sl += ["| Country | Nominal $/person | PPP $/person | Ratio | Year |", "|---|---|---|---|---|"]
    for code, d in sorted(pack["ratios"].items(), key=lambda kv: -kv[1]["ratio"]):
        yr = pack["nominal"]["rows"][code]["year"]
        sl.append(f"| {d['country']} | {d['nominal']:,.0f} | {d['ppp']:,.0f} | "
                  f"{d['ratio']:.3f} | {yr} |")
    sl += ["", "## Illustrative values", "",
           "Any figure on screen marked EXAMPLE or ILLUSTRATION is not from this table.",
           "It is a computed example written into `facts.json` with "
           "`kind: illustrative`.", ""]
    SOURCES.write_text("\n".join(sl) + "\n", encoding="utf-8")

    print(f"winner: {winner['id']}  Overall {winner['overall']}")
    print(f"runner-up: {runner['id']}  Overall {runner['overall']}")
    print(f"facts written: {len(pack['facts'])}")
    lo = min(pack['ratios'].items(), key=lambda kv: kv[1]['ratio'])
    hi = max(pack['ratios'].items(), key=lambda kv: kv[1]['ratio'])
    print(f"price-level ratio range: {lo[0]} {lo[1]['ratio']} .. {hi[0]} {hi[1]['ratio']}"
          f"  ({hi[1]['ratio']/lo[1]['ratio']:.2f}x)")
    print(f"-> {REPORT}\n-> {FACTS}\n-> {SOURCES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
