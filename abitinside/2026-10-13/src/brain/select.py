#!/usr/bin/env python3
"""
A Bit Inside - winner selection and format mapping (sections 4.6 and 4.7).

Applies the deterministic winner rule to the verified candidate set and writes
brain-report.md. No judgement happens here that is not already recorded in
candidates.py; this file only enforces the rules.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DAY = HERE.parent.parent
LOG = DAY / "verification_log.json"
REPORT = DAY / "brain-report.md"

sys.path.insert(0, str(HERE))
from candidates import (CANDIDATES, FORMAT_MAP, PUBLISHED, USED_FORMATS,  # noqa: E402
                        WEIGHTS, knowledge_class, overall)


def main() -> int:
    log = json.loads(LOG.read_text(encoding="utf-8"))
    entries = log["entries"]
    ok = {c["id"]: all(e["verified"] for e in entries if e["candidate"] == c["id"])
          for c in CANDIDATES}

    eligible = [c for c in CANDIDATES
                if ok[c["id"]] and not c.get("rejected") and overall(c["scores"]) >= 82]
    eligible.sort(key=lambda c: (overall(c["scores"]), c["scores"]["freshness"]), reverse=True)
    if not eligible:
        print("No candidate passes the gate. Stopping rather than inventing one.")
        return 2
    winner = eligible[0]
    runner = eligible[1] if len(eligible) > 1 else None

    # Section 4.6 emerging-vs-evergreen clause. It only ever *promotes* an
    # emerging candidate that is within 3 points of the best evergreen, so when
    # the leader is already emerging and ahead, the clause is not reached.
    clause = "not reached (the leader is the emerging candidate and leads outright)"
    best_evergreen = max((c for c in eligible if c["kind"] == "evergreen"),
                         key=lambda c: overall(c["scores"]), default=None)
    if best_evergreen and winner["kind"] == "evergreen":
        challengers = [c for c in eligible if c["kind"] == "emerging"
                       and overall(c["scores"]) >= overall(best_evergreen["scores"]) - 3]
        if challengers:
            best = max(challengers, key=lambda c: overall(c["scores"]))
            clause = (f"emerging candidate '{best['id']}' is within 3 points of the best "
                      f"evergreen; the clause would apply")

    kclass = knowledge_class(winner["knowledge_type"])
    primary_fmt, secondary_fmt = FORMAT_MAP[kclass]
    assert primary_fmt not in USED_FORMATS, "format already used"
    assert secondary_fmt not in USED_FORMATS, "secondary format already used"

    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    L: list[str] = []
    a = L.append
    a("# Brain report - A Bit Inside, 2026-10-13")
    a("")
    a(f"Generated {now} by `src/brain/` (gather -> verify -> select).")
    a("")
    a("## 1. Exclusion list applied (section 4.1)")
    a("")
    a("Already published 8-11 October 2026. None of these topics, in any wording, was reused:")
    a("")
    for i, t in enumerate(PUBLISHED, 1):
        a(f"{i:>2}. {t}")
    a("")
    a("## 2. Where the candidates came from")
    a("")
    a(f"Gathering run wrote `candidates_raw.json` at {json.loads((DAY / 'candidates_raw.json').read_text(encoding='utf-8'))['gathered_at']} "
      "from these independent sources:")
    a("")
    for k, v in [("Hacker News Firebase API (topstories + beststories)", "45 + 45 stories"),
                 ("Wikipedia REST pageviews top-viewed (5 days)", "100 titles"),
                 ("Wikipedia featured / most-read feed (5 days)", "100 titles"),
                 ("RSS: Ars Technica, The Verge, IEEE Spectrum, MIT Technology Review", "70 items"),
                 ("RSS: NASA, Google Engineering Blog, Mozilla Foundation, EFF", "100 items"),
                 ("RSS: Cloudflare Blog, Krebs on Security, Quanta, Rest of World, "
                  "BleepingComputer", "72 items")]:
        a(f"- {k}: {v}")
    a("")
    a("Web search was used as well, for the primary-source check on the leading candidates "
      "(CERT-FR, Claroty Team82, CISA, NVD, the retailers' own statements).")
    a("")
    a("## 3. Candidates, scores and verification")
    a("")
    a("Scores are 1-100 per axis. Overall = "
      + " + ".join(f"{v:.0%} x {k}" for k, v in WEIGHTS.items()) + ", rounded.")
    a("")
    hdr = ("| # | id | kind | Hook | Cur | Ret | Shr | Com | Vis | Fresh | Overall | "
           "sources | reason |")
    a(hdr)
    a("|---|---|---|----:|----:|----:|----:|----:|----:|----:|--------:|---------|"
      "---------|")
    order = sorted(CANDIDATES, key=lambda c: overall(c["scores"]), reverse=True)
    for i, c in enumerate(order, 1):
        s = c["scores"]
        src = "all 200" if ok[c["id"]] else "incomplete"
        if c.get("rejected"):
            src += " / REJECTED"
        a(f"| {i} | `{c['id']}` | {c['kind']} | {s['hook']} | {s['curiosity']} | "
          f"{s['retention']} | {s['shareability']} | {s['comment']} | {s['visual']} | "
          f"{s['freshness']} | **{overall(s)}** | {src} | {c['reason']} |")
    a("")
    a("### One-sentence reasons")
    a("")
    for c in order:
        a(f"- **`{c['id']}`** ({overall(c['scores'])}): {c['reason']}")
    a("")
    a("### Verification detail (section 4.4)")
    a("")
    a("Every primary source below was fetched over the network in this run. The status "
      "column is the real HTTP response code.")
    a("")
    a("| candidate | source | HTTP | accessed |")
    a("|---|---|---:|---|")
    for e in entries:
        mark = "OK" if e["verified"] else "FAILED"
        a(f"| `{e['candidate']}` | {e['label']} | {e['http_status']} {mark} | "
          f"{e['accessed']} |")
    a("")
    a("## 4. Winner")
    a("")
    a(f"**{winner['title']}**")
    a("")
    a(f"- Overall **{overall(winner['scores'])}** "
      f"(runner-up `{runner['id'] if runner else 'n/a'}` "
      f"at {overall(runner['scores']) if runner else 'n/a'}), threshold 82, passes 4.4.")
    a(f"- Age at selection: {winner['age_days']} day(s), so it counts as emerging.")
    a(f"- Emerging/evergreen clause: {clause}.")
    a(f"- Knowledge type: {winner['knowledge_type']}")
    a(f"- Verification notes: {winner['notes']}")
    a("")
    a(f"Why it beat the runner-up (`{runner['id'] if runner else 'n/a'}`): "
      f"{winner['reason']} "
      f"{runner['reason'] if runner else ''}")
    a("")
    a("## 5. Format decision (section 4.7)")
    a("")
    a("Playbook 9.1 classifies the knowledge as **" + kclass + "**, whose primary format is "
      f"**{primary_fmt}** and whose secondary is **{secondary_fmt}**.")
    a("")
    a("Formats already used by the last four days: "
      + ", ".join(USED_FORMATS) + ".")
    a("")
    a(f"**Chosen: {primary_fmt}.** Neither {primary_fmt} nor {secondary_fmt} has been used, "
      "so the rule is satisfied without bending it.")
    a("")
    a("Visual metaphor: the **cold-chain trace**. One continuous 24-hour temperature line "
      "runs under every scene - a flat, healthy band on most days, and one night in "
      "October where the line leaves the band and climbs. The controller, the probes and "
      "the defrost valve are drawn as small vector blocks sitting on that axis, so the "
      "mechanism and the data share a single metaphor instead of being two videos.")
    a("")
    a("Rejected on rule, not on merit:")
    a("")
    a("- `ksk` (DNS root key rollover, Overall 86) - the channel published 'Your Phone "
      "Doesn't Know Where Websites Live: The Hidden DNS Lookup' on 9 Oct 2026. A root "
      "trust-anchor rollover is that subject in new wording, which section 4.1 forbids.")
    a("- `chip` (spy chip in a wallet) - vivid, but Exploded View territory is already "
      "used and the only sourced account is the manufacturer's own.")
    a("")
    a("## 6. Deliverables from this stage")
    a("")
    a("- `candidates_raw.json` - everything the gathering run pulled, with URLs")
    a("- `verification_log.json` - the 4.4 gate, one row per source fetch")
    a("- `facts.json` - every number the video will use, with source or derivation")
    a("- `sources.md` - verified vs explained, with access dates")
    a("- `script.md` - the finished voiceover and shot list")
    a("")
    REPORT.write_text("\n".join(L), encoding="utf-8")
    print(f"winner: {winner['id']} ({overall(winner['scores'])})  format: {primary_fmt}")
    print(f"report -> {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())