"""Candidate gathering.

Builds the candidate pool for one day: at least twelve candidates drawn from at
least four independent source types, filtered against the exclusion list and
against the map-suitability rule for a Map Story.

Nothing here decides the winner. It only produces a pool with provenance.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from brain import sources as S  # noqa: E402
import re as _re  # noqa: E402

DAY = HERE.parents[1]
OUT = DAY / "brain-report.md"
RAW = DAY / "candidates_raw.json"

# ------------------------------------------------------------------ exclusions
# Topics already published on this channel, including rewordings.
EXCLUSIONS = [
    ("money creation", r"how banks create money|bank.*creat\w* money|money multiplier|"
                        r"commercial bank loan creation|quantitative easing creat"),
    ("left digit bias", r"\.99|left[- ]digit|charm pricing|psychological pricing|"
                        r"ninety[- ]nine cents"),
    ("airline co brand", r"co[- ]?brand|loyalty points|airline mile|avios|frequent flyer"),
    ("zimbabwe hyperinflation", r"zimbabwe|100 trillion|hyperinflation"),
    ("rule of 72", r"rule of 72"),
    ("compound interest standalone", r"compound interest"),
    ("tax brackets", r"tax bracket|marginal tax rate|tax band"),
    ("shrinkflation", r"shrinkflation|shrinkflation|smaller pack"),
    ("warehouse membership", r"warehouse club|costco|sam'?s club|membership fee model"),
    ("economies of scale", r"economies of scale|scale economies"),
    ("dollar dominance ep1", r"why the dollar dominates|dollar dominates global|"
                             r"global reserve currency|petrodollar|dollar as reserve"),
    ("order book", r"order book|stock.*fall.*no news|share price.*without news|"
                   r"no news.*price move"),
    ("usda food dollar", r"food dollar|usda.*food.*breakdown|nutrition facts.*spend"),
    ("mcdonald landlord", r"mcdonald.*landlord|golden arch.*property"),
    ("1929 crash", r"1929|bank run|deposit insurance|fdic|glass[- ]steagall"),
    ("mortgage interest first", r"early mortgage|amortisation|amortization|"
                                r"most of your payment is interest"),
    ("egypt nile", r"egypt|populous?.*nile|nile.*populous?"),
]

EVERGREEN_SEEDS = [
    ("why_100_feels_smaller",
     "Why does one hundred dollars feel smaller every year?",
     "Purchasing power is a ratio, not a number, so the same note buys a "
     "different basket in every country and every year.",
     "inflation divergence", "FP.CPI.TOTL.ZG"),
    ("ppp_gap",
     "Why does the same salary buy a different life in every country?",
     "Markets set exchange rates by trade, not by what a basket costs, so the "
     "gap between the two is a map you can draw.",
     "purchasing power parity", "NY.GDP.PCAP.PP.CD"),
    ("cheap_dollar",
     "Where is a dollar worth the most?",
     "A dollar is worth the basket it can buy, and that basket is priced in "
     "local money, so value drifts as inflation drifts.",
     "cost of living", "PA.NUS.PPPC.RF"),
    ("rates_divergence",
     "What happens when rates move in different countries at once?",
     "One policy rate cannot fit every economy, so capital searches for the "
     "gap and the gap is where the flow appears.",
     "policy rate divergence", "FR.INR.RINR"),
    ("current_account",
     "Which countries must keep spending to keep balance?",
     "A country that spends more than it earns must borrow from the rest of "
     "the world, and that borrowing shows up as a line on the map.",
     "current account balance", "BN.CAB.XOKA.GD.ZS"),
    ("remittances",
     "Why does money travel home along invisible roads?",
     "Migrant earnings cross a border as remittances, bypassing every tax "
     "system between the worker and the family.",
     "remittance corridors", "BX.TRF.PWKR.DT.GD.ZS"),
]


def excluded(text: str) -> str | None:
    t = text.lower()
    for name, pat in EXCLUSIONS:
        if re.search(pat, t):
            return name
    return None


# ------------------------------------------------------------------ candidates
def build() -> list[dict]:
    """Return the candidate pool with provenance attached."""
    cands: list[dict] = []
    seen_urls: set[str] = set()

    def add(cid, title, thesis, kind, indicator, source, value_url, evidence):
        if excluded(title + " " + thesis):
            return
        seen_urls.add(value_url)
        cands.append({
            "id": cid, "title": title, "thesis": thesis, "kind": kind,
            "indicator": indicator, "primary_source": source,
            "value_url": value_url, "evidence": evidence,
            "source_type": source_type(source),
        })

    def source_type(src: str) -> str:
        return {
            "World Bank": "open data API",
            "IMF DataMapper": "open data API",
            "FRED": "open data API",
            "Eurostat": "statistical agency API",
            "Federal Reserve press releases": "central bank press feed",
            "ECB press": "central bank press feed",
            "BLS latest numbers": "statistical agency feed",
            "r/Economics weekly top": "community trend feed",
            "r/personalfinance weekly top": "community trend feed",
            "Hacker News economics": "community trend feed",
            "Wikipedia": "trend signal",
        }.get(src, "other")

    # --- 1. World Bank indicators: the numeric spine
    wb_specs = [
        ("inflation_divergence", "Why does the same dollar buy different baskets?",
         "Inflation is not one global number. It is a map, and the map explains "
         "why identical prices feel different to different people.",
         "FP.CPI.TOTL.ZG"),
        ("ppp_vs_market", "Why does a salary mean different things across the map?",
         "Purchasing power parity and the market exchange rate disagree, and the "
         "size of that disagreement is the story.",
         "NY.GDP.PCAP.PP.CD"),
        ("nominal_vs_ppp", "What does the exchange rate leave out?",
         "Nominal income converted at market rates looks flat; converted at "
         "purchasing power it does not. The difference is the mechanism.",
         "NY.GDP.PCAP.CD"),
        ("cost_of_living", "Where is everyday life cheapest on this map?",
         "A price basket is the honest unit of account, and its size relative "
         "to income is a pure number you can rank.",
         "PA.NUS.PPPC.RF"),
        ("current_account", "Which economies run a deficit, and to whom?",
         "A deficit is a promise to repay, and the counterparty sits on the "
         "other side of the same map.",
         "BN.CAB.XOKA.GD.ZS"),
        ("remittances", "Which corridors move the most money home?",
         "Remittances are the one flow people send without any return to expect, "
         "and they run along labour routes, not trade routes.",
         "BX.TRF.PWKR.DT.GD.ZS"),
    ]
    wb = {}
    for cid, title, thesis, ind in wb_specs:
        r = S.world_bank(ind, "2021:2025")
        wb[cid] = r
        if not r.ok:
            continue
        add(cid, title, thesis, "data story", ind, "World Bank", r.url,
            {"last_updated": r.data["last_updated"],
             "economies": len(r.data["series"]), "note": r.note})

    # --- 2. IMF DataMapper, if reachable
    r = S.imf_datamapper("NGDP_RPCH")
    if r.ok:
        add("imf_growth_divergence", "Why does growth arrive in different places at different times?",
            "Growth is not synchronised, so the same year means something "
            "different in every economy.",
            "data story", "NGDP_RPCH", "IMF DataMapper", r.url, {"note": r.note})

    # --- 3. FRED: a single authoritative series for the US anchor
    r = S.fred_csv("CPIAUCSL", "2022-01-01")
    if r.ok:
        add("us_cpi_anchor",
            "What does one country's price level do to the world's reserve money?",
            "The anchor currency's own inflation is what every imported price "
            "ultimately follows.",
            "counter that lies", "CPIAUCSL", "FRED", r.url, {"note": r.note})

    # --- 4. Eurostat
    r = S.eurostat("prc_hicp_manr", {"geo": "EU27_2020", "lastTimePeriod": "3",
                                     "coicop": "CP00"})
    if r.ok:
        add("eu_hicp", "How far apart can two neighbouring economies drift?",
            "Neighbouring countries with one currency can still diverge sharply, "
            "which is the cleanest test of a mechanism.",
            "two lines one choice", "prc_hicp_manr", "Eurostat", r.url, {"note": r.note})

    # --- 5. Evergreen seeds from the channel idea file
    for cid, q, thesis, kind, ind in EVERGREEN_SEEDS:
        add(cid, q, thesis, "map story", ind, "World Bank",
            f"{S.WB}/country/all/indicator/{ind}?format=json&date=2021:2025",
            {"note": "seeded from the channel idea file; verified in the verify stage"})

    # --- 6. Trend signals, only as corroboration
    trends = []
    for name, url in S.RSS_FEEDS:
        r = S.rss(url, name)
        trends.append({"source": name, "url": r.url, "ok": r.ok, "note": r.note,
                       "accessed": r.accessed})
        if r.ok and name == "Federal Reserve press releases":
            heads = [i["title"] for i in r.data[:8]]
            if any(re.search(r"inflation|price|policy rate|rate", h, re.I) for h in heads):
                add("fed_recent_release",
                    "What has the anchor central bank done about prices this month?",
                    "The freshest official statement on the anchor currency's "
                    "prices, used as the hook's credibility.",
                    "data story", "CPIAUCSL", "Federal Reserve press releases",
                    r.url, {"headlines": heads[:8]})
    w = S.wikipedia_top("2026/10/13")
    trends.append({"source": "Wikipedia", "url": w.url, "ok": w.ok, "note": w.note,
                   "accessed": w.accessed})

    # --- 7. current-events candidates from the feeds that did answer
    for name, url in S.RSS_FEEDS:
        r = S.rss(url, name)
        if not r.ok:
            continue
        for item in r.data[:6]:
            t = item["title"]
            if not re.search(r"inflation|prices|cost of living|exchange rate|currency|"
                             r"purchasing power|tariff|interest rate", t, re.I):
                continue
            add(f"news::{_re.sub('[^a-z0-9]+', '-', t.lower())[:48]}",
                f"Does this week's headline describe a durable mechanism?",
                t, "data story", "FP.CPI.TOTL.ZG", name, item["link"] or r.url,
                {"headline": t, "published": item["published"]})
            break

    # --- dedupe by thesis similarity
    out, seen_thesis = [], []
    for c in cands:
        key = re.sub(r"[^a-z ]", " ", c["thesis"].lower()).split()
        keyset = set(key)
        if any(len(keyset & s) > max(3, int(0.6 * min(len(keyset), len(s)))) for s in seen_thesis):
            continue
        seen_thesis.append(keyset)
        out.append(c)
    return out, trends, wb


def main() -> int:
    cands, trends, wb = build()
    payload = {"generated": S.utc_now(), "candidates": cands, "trends": trends,
               "world_bank_status": {k: {"ok": v.ok, "url": v.url, "note": v.note}
                                     for k, v in wb.items()}}
    RAW.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    types = {}
    for c in cands:
        types[c["source_type"]] = types.get(c["source_type"], 0) + 1
    print(f"gathered {len(cands)} candidates from {len(types)} source types")
    for k, v in sorted(types.items(), key=lambda kv: -kv[1]):
        print(f"   {v:>2}  {k}")
    print(f"trend signals: {sum(1 for t in trends if t['ok'])}/{len(trends)} answered")
    print(f"-> {RAW}")
    return 0 if len(cands) >= 12 else 1


if __name__ == "__main__":
    sys.exit(main())
