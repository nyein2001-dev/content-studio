"""Live open-data fetchers for the content brain.

Everything here is keyless and free. Each function returns structured data plus
the exact URL and access timestamp, so every number that reaches the screen can
be traced back to the endpoint that produced it.

No endpoint is trusted: a failure returns None with a reason rather than raising,
so one dead host never stops the gather.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field

UA = "ArkadsLedger/1.0 (educational video production; contact via channel)"
TIMEOUT = 45


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Result:
    source: str
    url: str
    ok: bool
    data: object = None
    note: str = ""
    accessed: str = field(default_factory=utc_now)


def fetch(url: str, headers: dict | None = None, timeout: int = TIMEOUT,
          attempts: int = 3) -> tuple[bytes | None, str]:
    """GET with retries and backoff. Several open endpoints answer 403/429 when
    hit in a burst, so a single refusal is not treated as a dead host."""
    import time as _t

    last = ""
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(), f"HTTP {r.status}"
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code} {url}"
            if e.code in (400, 404, 410):
                break
            _t.sleep(1.5 * (i + 1) ** 2)      # 403/429: slow down and retry
        except Exception as e:                        # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
            _t.sleep(1.0 * (i + 1))
    return None, last


def fetch_json(url: str, **kw) -> tuple[object | None, str]:
    body, note = fetch(url, **kw)
    if body is None:
        return None, note
    try:
        return json.loads(body), note
    except json.JSONDecodeError as e:
        return None, f"{note} (bad JSON: {e})"


# ------------------------------------------------------------------ World Bank
WB = "https://api.worldbank.org/v2"


def world_bank(indicator: str, years: str = "2019:2025", per_page: int = 20000) -> Result:
    """One World Bank indicator for every country, newest years included."""
    url = (f"{WB}/country/all/indicator/{indicator}"
           f"?format=json&date={years}&per_page={per_page}")
    if per_page >= 20000:
        url = url.replace("per_page=20000", "per_page=1000") + "&mrnev=2"
    js, note = fetch_json(url)
    if not isinstance(js, list) or len(js) < 2:
        return Result("World Bank", url, False, note=note or "unexpected shape")
    meta, rows = js[0], js[1] or []
    last_updated = meta.get("lastupdated")
    data = {}
    for r in rows:
        c = r.get("country") or {}
        v = r.get("value")
        if v is None:
            continue
        data.setdefault(r["countryiso3code"] or c.get("id"), {}).update(
            {r["date"]: {"value": float(v), "country": c.get("value")}})
    return Result("World Bank", url, True,
                  {"indicator": indicator, "last_updated": last_updated, "series": data},
                  note=f"{len(data)} economies, lastupdated {last_updated}")


def world_bank_countries() -> Result:
    url = f"{WB}/country?format=json&per_page=400"
    js, note = fetch_json(url)
    if not isinstance(js, list) or len(js) < 2:
        return Result("World Bank", url, False, note=note)
    out = {}
    for r in js[1]:
        out[r["id"]] = {"name": r["name"], "region": r["region"]["value"],
                        "income": r["incomeLevel"]["value"]}
    return Result("World Bank", url, True, out, note=f"{len(out)} economies")


# ------------------------------------------------------------------ IMF
IMF = "https://www.imf.org/external/datamapper/api/v1"


def imf_datamapper(indicator: str) -> Result:
    url = f"{IMF}/{indicator}"
    js, note = fetch_json(url)
    if not isinstance(js, dict) or "values" not in js:
        return Result("IMF DataMapper", url, False, note=note or "no values block")
    block = js["values"].get(indicator, {})
    if not block:
        return Result("IMF DataMapper", url, False, note="indicator empty")
    latest = {}
    for c, series in block.items():
        yrs = sorted(y for y, v in series.items() if v is not None)
        if yrs:
            latest[c] = {"year": yrs[-1], "value": series[yrs[-1]]}
    meta = (js.get("api") or {}).get(indicator, {})
    return Result("IMF DataMapper", url, True,
                  {"indicator": indicator, "unit": meta.get("unit"),
                   "label": (js.get("indicators", {}).get(indicator, {}) or {}).get("label"),
                   "latest": latest},
                  note=f"{len(latest)} economies, newest {max(v['year'] for v in latest.values())}")


# ------------------------------------------------------------------ FRED
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def fred_csv(series: str, cosd: str = "2015-01-01") -> Result:
    url = f"{FRED}?id={series}&cosd={cosd}"
    body, note = fetch(url)
    if body is None:
        return Result("FRED", url, False, note=note)
    import csv
    import io

    rows = list(csv.DictReader(io.StringIO(body.decode("utf-8", "replace"))))
    if not rows:
        return Result("FRED", url, False, note="empty series")
    key = [k for k in rows[0] if k != "observation_date"][0]
    pts = [(r["observation_date"], float(r[key])) for r in rows if r[key] not in ("", ".")]
    return Result("FRED", url, True, {"series": series, "points": pts},
                  note=f"{len(pts)} points, last {pts[-1][0]} = {pts[-1][1]}")


# ------------------------------------------------------------------ Eurostat
EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"


def eurostat(dataset: str, params: dict) -> Result:
    q = "&".join(f"{k}={v}" for k, v in params.items()) + "&format=JSON&lang=EN"
    url = f"{EUROSTAT}/{dataset}?{q}"
    js, note = fetch_json(url)
    if not isinstance(js, dict) or "value" not in js:
        return Result("Eurostat", url, False, note=note or "no value block")
    return Result("Eurostat", url, True, {"dataset": dataset, "updated": js.get("updated"),
                                          "raw": js}, note=f"{len(js['value'])} cells")


# ------------------------------------------------------------------ RSS
def rss(url: str, source: str, limit: int = 25) -> Result:
    body, note = fetch(url)
    if body is None:
        return Result(source, url, False, note=note)
    import feedparser

    f = feedparser.parse(body)
    if not f.entries:
        return Result(source, url, False, note="no entries")
    items = [{"title": e.get("title", "").strip(),
              "link": e.get("link", ""),
              "published": e.get("published", ""),
              "summary": re.sub(r"<[^>]+>", " ", e.get("summary", ""))[:300]}
             for e in f.entries[:limit]]
    return Result(source, url, True, items, note=f"{len(items)} entries")


RSS_FEEDS = [
    ("Federal Reserve press releases", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("ECB press", "https://www.ecb.europa.eu/rss/press.html"),
    ("BLS latest numbers", "https://www.bls.gov/feed/bls_latest.rss"),
    ("IMF news", "https://www.imf.org/external/rss/feeds.aspx?category=News"),
    ("UNCTAD news", "https://unctad.org/rss/news.xml"),
    ("Bank of England", "https://www.bankofengland.co.uk/boeapps/rss/feeds.aspx?feed=News"),
    ("r/Economics weekly top", "https://www.reddit.com/r/economics/top/.rss?t=week"),
    ("r/personalfinance weekly top", "https://www.reddit.com/r/personalfinance/top/.rss?t=week"),
    ("Hacker News economics", "https://hnrss.org/newest?q=economics&count=20"),
]


# ------------------------------------------------------------------ Wikipedia
WIKI = "https://api.wikimedia.org/feed/v1/wikipedia/en/featured"


def wikipedia_top(day: str) -> Result:
    url = f"{WIKI}/{day}"
    js, note = fetch_json(url)
    if not isinstance(js, dict):
        return Result("Wikipedia", url, False, note=note)
    titles = []
    for key in ("mostread", "featured"):
        for art in (js.get(key) or {}).get("articles", [])[:60]:
            titles.append(art.get("title", ""))
    return Result("Wikipedia", url, True, sorted(set(t for t in titles if t)),
                  note=f"{len(set(titles))} titles")


# ------------------------------------------------------------------ OWID / BIS / OECD
OWID_CANDIDATES = {
    "inflation": "https://ourworldindata.org/grapher/cpi-inflation.csv?csvType=filtered",
    "gdp_per_capita_ppp": "https://ourworldindata.org/grapher/gdp-per-capita-worldbank.csv?csvType=filtered",
    "life_expectancy": "https://ourworldindata.org/grapher/life-expectancy.csv?csvType=filtered",
}


def owid_csv(slug: str) -> Result:
    url = OWID_CANDIDATES.get(slug, f"https://ourworldindata.org/grapher/{slug}.csv?csvType=filtered")
    body, note = fetch(url)
    if body is None:
        return Result("Our World in Data", url, False, note=note)
    import csv
    import io

    rows = list(csv.DictReader(io.StringIO(body.decode("utf-8", "replace"))))
    return Result("Our World in Data", url, True, {"slug": slug, "rows": rows[:4000]},
                  note=f"{len(rows)} rows")


def bis_series(codes: tuple[str, ...] = ("IR3TIB01XTM156N", "IR3TIB01JPM156N",
                                        "IR3TIB01EZM156N", "IR3TIB01AUM156N")) -> Result:
    """BIS policy rates via the public SDMX API."""
    out = {}
    for c in codes:
        url = (f"https://stats.bis.org/api/v1/data/WS_CB/{c}"
               f"?startPeriod=2023-01&format=csv")
        body, note = fetch(url, timeout=60)
        if body is None:
            out[c] = {"ok": False, "note": note}
            continue
        lines = body.decode("utf-8", "replace").splitlines()
        out[c] = {"ok": len(lines) > 1, "rows": len(lines) - 1, "head": lines[:3]}
    return Result("BIS", "https://stats.bis.org/api/v1/data/WS_CB", True, out,
                  note="; ".join(f"{k}:{v.get('rows', v.get('note'))}" for k, v in out.items()))


def oecd_prices() -> Result:
    url = ("https://sdmx.oecd.org/public/rest/data/"
           "OECD.SDD.TPS,DSD_REV_COMP@DF_RCOMP,1.0/.?startPeriod=2024&dimension_at_observation=AllDimensions")
    body, note = fetch(url, headers={"Accept": "text/csv"}, timeout=90)
    if body is None:
        return Result("OECD", url, False, note=note)
    lines = body.decode("utf-8", "replace").splitlines()
    return Result("OECD", url, True, {"rows": max(0, len(lines) - 1)},
                  note=f"{max(0, len(lines)-1)} rows")


# ------------------------------------------------------------------ helpers
def latest_common_years(series: dict[str, dict[str, dict]], years: int = 1) -> dict:
    """For each country, the newest year, and optionally the N years before."""
    out = {}
    for code, pts in series.items():
        ys = sorted(pts, reverse=True)
        if ys:
            out[code] = {"name": pts[ys[0]]["country"], "year": ys[0],
                         "value": pts[ys[0]]["value"],
                         "prev": [{"year": y, "value": pts[y]["value"]} for y in ys[1:years + 1]]}
    return out


def fmt(value: float, unit: str) -> str:
    if unit in ("percent", "%"):
        return f"{value:,.1f}%"
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")
