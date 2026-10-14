#!/usr/bin/env python3
"""
A Bit Inside - candidate gathering (section 4.3).

Pulls free, key-less sources and writes candidates_raw.json:
  * Hacker News Firebase API      (top + best stories)
  * Wikipedia top-viewed pages    (REST pageviews API) and the featured feed
  * RSS from primary / authoritative outlets
  * an evergreen mechanism shortlist is added later by candidates.py

Nothing here decides anything. This module only collects evidence with a URL and a
retrieval timestamp, so every later claim can be traced back.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DAY = HERE.parent.parent
RAW = DAY / "candidates_raw.json"

UA = "A-Bit-Inside/1.0 (https://abitinside.example/; research) python-urllib/3.11"

RSS_FEEDS = {
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "IEEE Spectrum": "https://spectrum.ieee.org/feeds/feed.rss",
    "MIT Technology Review": "https://www.technologyreview.com/feed/",
    "NASA": "https://www.nasa.gov/rss/dyn/breaking_news.rss",
    "Google Engineering Blog": "https://developers.googleblog.com/feeds/posts/default",
    "Cloudflare Blog": "https://blog.cloudflare.com/rss/",
    "Cloudflare Learning": "https://blog.cloudflare.com/tag/network/rss/",
    "Mozilla Foundation": "https://foundation.mozilla.org/en/blog/rss/",
    "EFF": "https://www.eff.org/rss/updates.xml",
    " Krebs on Security": "https://krebsonsecurity.com/feed/",
    "WIRED Security": "https://www.wired.com/feed/tag/security/latest/rss",
    "Quanta Magazine": "https://api.quantamagazine.org/feed/",
    "Rest of World": "https://restofworld.org/feed/latest/",
    "Bleeping Computer": "https://www.bleepingcomputer.com/feed/",
}

HN_TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_BEST = "https://hacker-news.firebaseio.com/v0/beststories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{id}.json"
WIKI_TOPVIEWS = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/top/"
                 "en.wikipedia/all-access/{y}/{m:02d}/{d:02d}")
WIKI_MOSTREAD = ("https://en.wikipedia.org/api/rest_v1/feed/featured/"
                 "{y}/{m:02d}/{d:02d}")


def get(url: str, timeout: int = 25):
    """GET with a retry/backoff. Wikimedia rate-limits bursts with 400/429."""
    last = None
    for attempt in range(5):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code in (400, 429, 500, 502, 503):
                time.sleep(8.0 * (attempt + 1))
                continue
            raise
        except Exception as exc:  # noqa: BLE001 - transient network faults
            last = exc
            time.sleep(5.0 * (attempt + 1))
    raise last if last else RuntimeError(f"GET failed: {url}")


def get_json(url: str, timeout: int = 25):
    status, body = get(url, timeout)
    return status, json.loads(body.decode("utf-8", "replace"))


def strip_html(s: str) -> str:
    s = re.sub(r"<script.*?</script>", " ", s or "", flags=re.S | re.I)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def hn_stories(list_url: str, label: str, limit: int = 45) -> list[dict]:
    try:
        _, ids = get_json(list_url)
    except Exception as exc:  # noqa: BLE001
        print(f"  {label}: FAILED {exc}")
        return []
    out = []
    for i, sid in enumerate(ids[:limit]):
        try:
            _, item = get_json(HN_ITEM.format(id=sid))
        except Exception:  # noqa: BLE001
            continue
        if not item or item.get("type") != "story" or not item.get("title"):
            continue
        out.append({
            "source": f"Hacker News ({label})",
            "title": item["title"],
            "url": item.get("url") or f"https://news.ycombinator.com/item?id={sid}",
            "discussion": f"https://news.ycombinator.com/item?id={sid}",
            "score": item.get("score"),
            "hn_date": dt.datetime.utcfromtimestamp(item["time"]).isoformat() + "Z"
            if item.get("time") else None,
            "retrieved": NOW,
        })
        if (i + 1) % 15 == 0:
            print(f"  {label}: {len(out)} stories")
    return out


def rss_items(name: str, url: str) -> list[dict]:
    import feedparser

    try:
        status, body = get(url, timeout=30)
    except Exception as exc:  # noqa: BLE001
        print(f"  {name}: FAILED {type(exc).__name__} {exc}")
        return []
    f = feedparser.parse(body)
    items = []
    for e in f.entries[:60]:
        pub = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
        items.append({
            "source": name,
            "title": getattr(e, "title", ""),
            "url": getattr(e, "link", ""),
            "summary": strip_html(getattr(e, "summary", ""))[:600],
            "published": dt.datetime(*pub[:6]).isoformat() if pub else None,
            "feed_http": status,
            "retrieved": NOW,
        })
    print(f"  {name}: {len(items)} items (HTTP {status})")
    return items


def wiki_topviewed(days: list[str]) -> list[dict]:
    out = []
    for d in days:
        url = WIKI_TOPVIEWS.format(y=d[:4], m=int(d[5:7]), d=int(d[8:10]))
        try:
            _, data = get_json(url)
        except Exception as exc:  # noqa: BLE001
            print(f"  wikipedia topviews {d}: FAILED {exc}")
            continue
        arts = data.get("items", [{}])[0].get("articles", [])
        for rank, a in enumerate(arts[:25], 1):
            out.append({
                "source": f"Wikipedia top viewed ({d})",
                "title": a.get("article", "").replace("_", " "),
                "url": f"https://en.wikipedia.org/wiki/{a.get('article', '')}",
                "rank": rank,
                "views": a.get("views"),
                "retrieved": NOW,
            })
        print(f"  wikipedia topviews {d}: {len(arts)} titles")
        time.sleep(1.2)
    return out


def wiki_featured(days: list[str]) -> list[dict]:
    out = []
    for d in days:
        url = WIKI_MOSTREAD.format(y=d[:4], m=int(d[5:7]), d=int(d[8:10]))
        try:
            _, data = get_json(url)
        except Exception as exc:  # noqa: BLE001
            print(f"  wikipedia featured {d}: FAILED {exc}")
            continue
        for e in data.get("mostread", {}).get("articles", [])[:25]:
            out.append({
                "source": f"Wikipedia featured ({d})",
                "title": e.get("title", ""),
                "url": e.get("content_urls", {}).get("desktop", {}).get("page", ""),
                "views": e.get("views"),
                "retrieved": NOW,
            })
        print(f"  wikipedia featured {d}: {data.get('mostread', {}).get('articles', [{}])[0].get('title', '?')}")
        time.sleep(1.2)
    return out


NOW = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else "all"
    print(f"A Bit Inside - gathering candidates at {NOW}")
    data: dict[str, list] = {}
    if RAW.exists() and only != "all":
        data = json.loads(RAW.read_text(encoding="utf-8"))["data"]
        print(f"(resuming, keeping {len(data)} previously gathered groups)")

    # Each source group is independent. A group that fails (rate limiting, a DNS
    # stall) is reported and carried on with, because the run still has several
    # independent sources. Only a run that collects nothing at all is a failure.
    failures: list[str] = []

    if only in ("all", "hn"):
        print("Hacker News")
        try:
            data["hn_top"] = hn_stories(HN_TOP, "top")
            data["hn_best"] = hn_stories(HN_BEST, "best")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"hacker news: {exc}")
            print(f"  hacker news unavailable: {exc}")

    if only in ("all", "wiki"):
        print("Wikipedia")
        try:
            days = [(dt.date.today() - dt.timedelta(days=i)).isoformat() for i in range(0, 15)]
            data["wiki_topviewed"] = wiki_topviewed(days[:5])
            data["wiki_featured"] = wiki_featured(days[:5])
        except Exception as exc:  # noqa: BLE001
            failures.append(f"wikipedia: {exc}")
            print(f"  wikipedia unavailable: {exc}")

    if only in ("all", "rss"):
        print("RSS")
        data["rss"] = [it for name, url in RSS_FEEDS.items() for it in rss_items(name, url)]

    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_text(json.dumps({"gathered_at": NOW, "feeds": RSS_FEEDS,
                               "source_failures": failures, "data": data},
                              indent=1, ensure_ascii=False), encoding="utf-8")
    counts = {k: len(v) for k, v in data.items()}
    total = sum(counts.values())
    print("\ntotals:", counts, "->", RAW)
    if total == 0:
        print("\nNOTHING COLLECTED: every source failed. Stopping rather than guessing.")
        return 1
    live = sum(len(v) for k, v in data.items() if k != "rss") + len(data.get("rss", []))
    outlets = {i["source"] for i in data.get("rss", [])}
    outlets |= {"Hacker News", "Wikipedia"}
    print(f"\n{len(outlets)} independent sources, {live} items collected")
    if failures:
        print("partial run, these sources were unavailable: " + "; ".join(failures))
    return 0


if __name__ == "__main__":
    sys.exit(main())