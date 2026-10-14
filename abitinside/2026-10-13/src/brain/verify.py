#!/usr/bin/env python3
"""
A Bit Inside - the section 4.4 verification gate.

Fetches every primary/authoritative source behind every candidate, records the
HTTP status, byte count and access date, and writes verification_log.json.
qa.py re-checks the winners of this log in the same run, so a source that rots
between research and delivery fails the build.
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
LOG = DAY / "verification_log.json"

sys.path.insert(0, str(HERE))
from candidates import CANDIDATES, overall  # noqa: E402

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 ABitInside/1.0 research")


def fetch(url: str, timeout: int = 30) -> tuple[int, int, str]:
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-GB,en;q=0.9",
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read(400_000)
                return r.status, len(body), body.decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(4 * (attempt + 1))
                continue
            return e.code, 0, ""
        except Exception as e:  # noqa: BLE001
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue
            return 0, 0, f"{type(e).__name__}: {e}"
    return 0, 0, "unreachable"


def main() -> int:
    now = dt.datetime.now(dt.timezone.utc)
    entries = []
    for c in CANDIDATES:
        print(f"\n[{c['id']}] {c['title'][:74]}")
        for label, url in c["primary"]:
            status, n, body = fetch(url)
            title = ""
            if body:
                m = re.search(r"<title[^>]*>(.*?)</title>", body, re.S | re.I)
                if m:
                    title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip()[:110]
            ok = status == 200
            print(f"   {'OK ' if ok else 'BAD'} {status} {n:>7}b  {label[:62]}")
            entries.append({
                "candidate": c["id"], "label": label, "url": url,
                "http_status": status, "bytes": n,
                "page_title": title,
                "accessed": now.isoformat(timespec="seconds"),
                "verified": ok,
            })
            time.sleep(0.8)

    passing = [c for c in CANDIDATES
               if all(e["verified"] for e in entries if e["candidate"] == c["id"])
               and not c.get("rejected")]
    LOG.write_text(json.dumps({
        "checked_at": now.isoformat(timespec="seconds"),
        "note": "Section 4.4 gate: every primary source was fetched over the network in "
                "this run. http_status is the real response code.",
        "entries": entries,
    }, indent=1), encoding="utf-8")

    print("\n" + "=" * 78)
    for c in CANDIDATES:
        st = all(e["verified"] for e in entries if e["candidate"] == c["id"])
        rej = f"  REJECTED: {c['rejected']}" if c.get("rejected") else ""
        print(f"{c['id']:<12} overall={overall(c['scores']):>3}  "
              f"sources {'all 200' if st else 'INCOMPLETE'}{rej}")
    print("=" * 78)
    print(f"{len(passing)} candidates pass the verification gate: "
          f"{[c['id'] for c in passing]}")
    print(f"log -> {LOG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())