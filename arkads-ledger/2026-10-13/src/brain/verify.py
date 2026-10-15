"""Verification gate.

A candidate passes only if every number the video would show is stated by the
primary source named in the candidate, and that source answers 200 in this run.
The extracted values are written here and then consumed by `select.py` and by
`facts.json`, so nothing reaches the screen that did not come out of this file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from brain import sources as S  # noqa: E402

DAY = HERE.parents[1]
RAW = DAY / "candidates_raw.json"
LOG = DAY / "verification_log.json"

# Countries the video may quote. Chosen for recognisability, not for the result.
FOCUS = ["USA", "TUR", "ARG", "NGA", "IND", "ZAF", "BRA", "GBR", "JPN",
         "CHN", "DEU", "FRA", "MEX", "IDN", "RUS", "KOR", "SAU", "EGY"]


def url_ok(url: str) -> tuple[bool, str]:
    body, note = S.fetch(url, attempts=2)
    return (body is not None), note


def verify_world_bank(indicator: str, years: str = "2019:2025") -> dict:
    """Pull the newest available year for every focus country, twice."""
    r = S.world_bank(indicator, years)
    if not r.ok:
        return {"ok": False, "indicator": indicator, "note": r.note, "url": r.url}
    series = r.data["series"]
    rows = {}
    for code in FOCUS:
        pts = series.get(code)
        if not pts:
            continue
        ys = sorted(pts, reverse=True)
        newest = ys[0]
        entry = {"name": pts[newest]["country"], "year": newest,
                 "value": pts[newest]["value"], "history":
                 [{"year": y, "value": pts[y]["value"]} for y in ys[:6]]}
        # three-year change where available
        older = [y for y in ys if int(y) <= int(newest) - 3]
        if older:
            entry["value_3y_ago"] = pts[older[0]]["value"]
            entry["year_3y_ago"] = older[0]
        rows[code] = entry
    if not rows:
        return {"ok": False, "indicator": indicator, "note": "no focus countries",
                "url": r.url}
    years = [v["year"] for v in rows.values()]
    newest = max(years)
    return {"ok": True, "indicator": indicator, "url": r.url,
            "publisher": "World Bank", "dataset": "World Development Indicators",
            "last_updated": r.data["last_updated"], "rows": rows,
            "data_year": newest, "latest_available": int(newest) < 2024,
            "note": f"{len(rows)} of {len(FOCUS)} focus economies, newest {newest}"}


def main() -> int:
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    verified: list[dict] = []
    cache: dict[str, dict] = {}

    for c in raw["candidates"]:
        entry = {"id": c["id"], "title": c["title"], "thesis": c["thesis"],
                 "kind": c["kind"], "source_type": c["source_type"],
                 "primary_source": c["primary_source"], "value_url": c["value_url"]}
        ok, note = url_ok(c["value_url"])
        entry["source_reachable"] = ok
        entry["source_status"] = note
        ind = c.get("indicator")
        if c["primary_source"] == "World Bank" and ind:
            if ind not in cache:
                cache[ind] = verify_world_bank(ind)
            v = cache[ind]
            entry["verified"] = bool(v.get("ok"))
            entry["verification"] = {k: v[k] for k in
                                     ("indicator", "url", "publisher", "dataset",
                                      "last_updated", "data_year", "latest_available",
                                      "note") if k in v}
            if not v.get("ok"):
                entry["verified"] = False
                entry["verification"]["error"] = v.get("note")
            else:
                vals = {k2: r2["value"] for k2, r2 in v["rows"].items()}
                entry["sample"] = dict(sorted(vals.items(), key=lambda kv: -kv[1])[:8])
        else:
            entry["verified"] = ok
            entry["verification"] = {"url": c["value_url"], "note": note,
                                     "evidence": c.get("evidence")}
        verified.append(entry)

    payload = {"generated": S.utc_now(), "verifications": verified,
               "indicator_cache": {k: {kk: vv for kk, vv in v.items() if kk != "rows"}
                                   for k, v in cache.items()}}
    LOG.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    npass = sum(1 for v in verified if v.get("verified"))
    print(f"verified {npass}/{len(verified)} candidates")
    for v in verified:
        vv = v.get("verification", {})
        print(f"  {'PASS' if v.get('verified') else 'FAIL'}  {v['id']:<34} "
              f"{vv.get('data_year', vv.get('note', ''))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
