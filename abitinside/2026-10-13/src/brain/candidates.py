#!/usr/bin/env python3
"""
A Bit Inside - the candidate set and the scoring rubric (section 4).

Each candidate records where it came from, which primary source backs every claim
we intend to make, and the seven editorial scores from section 4.5. Nothing here is
invented: every URL in `sources` was fetched by verify.py in this run and the HTTP
status is recorded in verification_log.json.
"""
from __future__ import annotations

# Exclusion list (section 4.1) - already published 8-11 Oct 2026, never reused.
PUBLISHED = [
    "tap-to-pay / payment tokens",
    "touchscreen capacitive sensing",
    "DNS lookup",
    "iPhone 18 Pro variable aperture",
    'GPT-6 "Intelligent UI"',
    "QR-code error correction",
    "GPS + relativity",
    "AI agents / Gemini agent loop",
    "digital legacy / afterlife",
    "Google Playground",
    'AI tokens ("strawberry")',
    "file deletion / TRIM",
    "undersea cables",
    "link rot",
    "Honda wireless charging road",
    "diffusion image generation",
    "bot traffic share",
    "Year 2038",
    "Voyager 1 light-day",
    "Face ID dot projector",
]

# Formats already used by the last four published days (section 4.7).
USED_FORMATS = [
    "Step-by-Step", "Myth->Mechanism", "Terminal Explains", "Exploded View",
    "Before/After", "Progressive Reveal", "Systems Diagram", "Interface Autopsy",
]

WEIGHTS = {
    "hook": 0.20,
    "curiosity": 0.20,
    "retention": 0.15,
    "shareability": 0.15,
    "comment": 0.10,
    "visual": 0.10,
    "freshness": 0.10,
}

# --------------------------------------------------------------------------
# Candidates. `evidence` = where it surfaced in today's gathering run.
# `primary` = the authoritative pages that must return HTTP 200 before the
#             candidate may be used (section 4.4).
# --------------------------------------------------------------------------
CANDIDATES = [
    {
        "id": "fridge",
        "title": "Attackers heated hundreds of French supermarket fridges to 50 C by hijacking "
                 "the store's refrigeration controller",
        "kind": "emerging",
        "age_days": 1,
        "knowledge_type": "A quantity changing over time (case temperature) caused by a "
                          "system (controller + probes + defrost valve)",
        "evidence": [
            "Ars Technica RSS 2026-10-12 'Cyberattack shuts down refrigerators at French "
            "supermarkets'",
            "Hacker News best story, 717 points, 'Hackers activate automatic defrosting in "
            "supermarket fridges across Europe'",
            "BleepingComputer RSS 2026-10-12",
            "The Hacker News 2026-10-13 'Attackers Heat French Supermarket Fridges Up to 50C'",
        ],
        "primary": [
            ("CERT-FR / ANSSI alert CERTFR-2026-ALE-012, 12 Oct 2026",
             "https://www.cert.ssi.gouv.fr/alerte/CERTFR-2026-ALE-012/"),
            ("Claroty Team82, 'France Supermarket Hacks Expose Risks of Internet-Facing "
             "Refrigeration Systems', 12 Oct 2026",
             "https://www.claroty.com/blog/france-supermarket-hacks-expose-risks-of-"
             "internet-facing-refrigeration-systems"),
            ("NVD entry for CVE-2025-41450 (Danfoss AK-SM 8xxA authentication bypass)",
             "https://nvd.nist.gov/vuln/detail/CVE-2025-41450"),
        ],
        "notes": "Government CSIRT alert plus vendor-research plus NVD: the strongest "
                 "verification position of the whole set. Nothing depends on a claim only "
                 "one outlet makes, and the unknowns (which flaw, who, how) are stated as "
                 "unknown by CERT-FR itself.",
        "scores": {"hook": 94, "curiosity": 92, "retention": 91, "shareability": 92,
                   "comment": 88, "visual": 90, "freshness": 97},
        "reason": "A fridge is something everyone recognises, the number (50 C) is absurd on "
                  "its face, and the mechanism - one small web server behind the cabinets - "
                  "is genuinely inside the technology.",
    },
    {
        "id": "fingerprint",
        "title": "Your browser is the cookie: how a site recognises you with no cookie stored",
        "kind": "evergreen",
        "age_days": 4000,
        "knowledge_type": "A process / sequence (probe -> hash -> identify) plus a hidden "
                          "part of a product",
        "evidence": [
            "Hacker News best story, 722 points, 'Fingerprints are the new cookies'",
            "Alias Research, 'Browser fingerprinting in 2026: which signals actually identify "
            "you', 15 Jun 2026",
        ],
        "primary": [
            ("EFF Panopticlick / Cover Your Tracks, 'How Unique Is Your Web Browser?'",
             "https://panopticlick.eff.org/"),
            ("W3C, Fingerprinting Guidance (First Public Working Draft)",
             "https://www.w3.org/TR/fingerprinting-guidance/"),
            ("arXiv:2606.26412, 'A Measurement Study of WebGPU Privacy'",
             "https://arxiv.org/abs/2606.26412"),
        ],
        "notes": "Fully evergreen and the most 'digital life' topic on the list, but the "
                 "fresh hook is weak and the strongest entropy numbers in circulation are "
                 "vendor/secondary rather than primary.",
        "scores": {"hook": 86, "curiosity": 89, "retention": 88, "shareability": 86,
                   "comment": 91, "visual": 92, "freshness": 58},
        "reason": "Strong mechanism and huge comment potential, but the hook is an idea "
                  "rather than a dated fact, and it leans on secondary entropy tables.",
    },
    {
        "id": "ksk",
        "title": "The DNS root changed its signing key on 11 October 2026",
        "kind": "emerging",
        "age_days": 7,
        "knowledge_type": "A system / cause-effect chain (root key -> resolver -> every lookup)",
        "evidence": [
            "Cloudflare Blog 2026-10-06, 'The keys to the Internet change on October 11. "
            "Are you ready?'",
        ],
        "primary": [
            ("IANA, Root Zone Key Signing Key rollover (KSK-2024)",
             "https://www.iana.org/domains/root/ksk-2024"),
            ("RFC 5011, Trust Anchor Automation",
             "https://www.rfc-editor.org/rfc/rfc5011"),
        ],
        "notes": "REJECTED on the exclusion list: the channel already published 'Your Phone "
                 "Doesn't Know Where Websites Live: The Hidden DNS Lookup' on 9 Oct 2026. "
                 "The mechanism is a DNS trust-anchor rollover; that is the same subject "
                 "area in new wording, which section 4.1 forbids.",
        "scores": {"hook": 90, "curiosity": 87, "retention": 84, "shareability": 85,
                   "comment": 80, "visual": 84, "freshness": 93},
        "reason": "Strong on paper, but it is the same territory as the published DNS "
                  "video, so it is excluded before scoring can promote it.",
        "rejected": "exclusion list (DNS)",
    },
    {
        "id": "passkeys",
        "title": "Passkeys: what actually replaces your password",
        "kind": "evergreen",
        "age_days": 3000,
        "knowledge_type": "A process / sequence (challenge -> signature -> key stays on device)",
        "evidence": [
            "Hacker News best story, 1066 points, 'Passkeys are a trap'",
        ],
        "primary": [
            ("W3C Web Authentication Level 3 recommendation",
             "https://www.w3.org/TR/webauthn-3/"),
            ("FIDO Alliance, Passkeys overview",
             "https://passkeys.dev/"),
        ],
        "notes": "Verifiable primary sources exist. The problem is editorial: the hook in "
                 "circulation is an opinion piece, and the channel has already published a "
                 "security-flavoured explainer set.",
        "scores": {"hook": 84, "curiosity": 83, "retention": 85, "shareability": 84,
                   "comment": 93, "visual": 78, "freshness": 45},
        "reason": "Strong comment bait, but the mechanism is abstract to show and the "
                  "top-of-feed framing is contested opinion, not fact.",
    },
    {
        "id": "resumable",
        "title": "How a 40 GB download survives a dropped connection",
        "kind": "evergreen",
        "age_days": 2000,
        "knowledge_type": "A process / sequence (range request -> chunk -> rejoin)",
        "evidence": [
            "Hacker News top story, 218 points, 'Making big downloads resumable in Firefox'",
        ],
        "primary": [
            ("RFC 9110, HTTP Semantics - Range requests",
             "https://www.rfc-editor.org/rfc/rfc9110.html"),
            ("MDN, HTTP range requests",
             "https://developer.mozilla.org/en-US/docs/Web/HTTP/Range_requests"),
        ],
        "notes": "Completely verifiable and very visual (byte-range bar, chunks re-joining).",
        "scores": {"hook": 80, "curiosity": 82, "retention": 83, "shareability": 82,
                   "comment": 76, "visual": 88, "freshness": 42},
        "reason": "Excellent little mechanism, but a weak hook and a small story: there is "
                  "no dated fact to open on.",
    },
    {
        "id": "pqc",
        "title": "Post-quantum keys went live on the public internet this month",
        "kind": "emerging",
        "age_days": 10,
        "knowledge_type": "A process / sequence inside a protocol (key exchange)",
        "evidence": [
            "Cloudflare Blog, Birthday Week 2026 wrap-up (post-quantum security)",
        ],
        "primary": [
            ("NIST, Post-Quantum Cryptography Standardization (FIPS 203/204/205)",
             "https://csrc.nist.gov/projects/post-quantum-cryptography"),
            ("Cloudflare Blog, Birthday Week 2026",
             "https://blog.cloudflare.com/birthday-week-2026-wrap-up/"),
        ],
        "notes": "Real and well sourced, but the story is a platform announcement rather "
                 "than a single mechanism a viewer can picture.",
        "scores": {"hook": 82, "curiosity": 86, "retention": 83, "shareability": 83,
                   "comment": 78, "visual": 80, "freshness": 86},
        "reason": "Interesting and timely, but the explainable core (lattice maths) is hard "
                  "to make honest and visual in 100 seconds.",
    },
    {
        "id": "agever",
        "title": "Age verification: how 'prove you're an adult' actually works online",
        "kind": "emerging",
        "age_days": 5,
        "knowledge_type": "A product / workflow with an interface",
        "evidence": [
            "EFF, 'When No ID Means No Internet: Age Verification and the Right to Access "
            "Information', 8 Oct 2026",
        ],
        "primary": [
            ("EFF, When No ID Means No Internet",
             "https://www.eff.org/deeplinks/2026/10/when-no-id-means-no-internet-age-"
             "verification-and-right-access-information"),
            ("Ofcom, Age assurance guidance",
             "https://www.ofcom.org.uk/phones-and-broadband/protecting-children/age-assurance"),
        ],
        "notes": "Genuinely digital-life, but the mechanism differs per provider and the "
                 "policy details are moving week to week.",
        "scores": {"hook": 81, "curiosity": 84, "retention": 80, "shareability": 88,
                   "comment": 95, "visual": 76, "freshness": 84},
        "reason": "Enormous comment potential, but it is a policy story rather than a "
                  "mechanism you can point at inside a device.",
    },
    {
        "id": "grindr",
        "title": "Norway fined an advertising firm over how it shared location data",
        "kind": "emerging",
        "age_days": 1,
        "knowledge_type": "A system / cause-effect (identifiers flowing between parties)",
        "evidence": [
            "BleepingComputer 2026-10-12, 'Norway fines Microsoft ad firm $9.6 million over "
            "Grindr data sharing'",
        ],
        "primary": [
            ("Datatilsynet (Norwegian Data Protection Authority), press release",
             "https://www.datatilsynet.no/aktuelt/"),
        ],
        "notes": "Single-regulator press release; no independent technical primary source "
                 "and no mechanism to show inside a device.",
        "scores": {"hook": 79, "curiosity": 80, "retention": 76, "shareability": 82,
                   "comment": 88, "visual": 68, "freshness": 94},
        "reason": "A legal outcome, not a mechanism: nothing on screen would be a picture of "
                  "how anything works.",
    },
    {
        "id": "intel",
        "title": "A GPU accelerator with up to 480 GB of memory on the package",
        "kind": "emerging",
        "age_days": 2,
        "knowledge_type": "A product spec",
        "evidence": ["Hacker News top story, 226 points, Intel D270 GPU AI Accelerator"],
        "primary": [("Intel, Data Center GPU D-series product page",
                     "https://www.intel.com/content/www/us/en/products/details/discrete-gpus/"
                     "data-center-gpu/d-series.html")],
        "notes": "Primary source exists but it is a marketing product page.",
        "scores": {"hook": 76, "curiosity": 77, "retention": 72, "shareability": 74,
                   "comment": 72, "visual": 70, "freshness": 90},
        "reason": "A spec sheet is not an explanation: nothing here is a mechanism a "
                  "viewer can follow.",
    },
    {
        "id": "jan",
        "title": "Running a language model larger than RAM by streaming experts from SSD",
        "kind": "emerging",
        "age_days": 1,
        "knowledge_type": "A system / cause-effect (memory tiering)",
        "evidence": ["Hacker News top story, 153 points, 'Janas'"],
        "primary": [("Project repository", "https://github.com/prabanta-dev/janas")],
        "notes": "Interesting but hours old, unreviewed, and the only source is the author's "
                 "own repository.",
        "scores": {"hook": 80, "curiosity": 86, "retention": 74, "shareability": 76,
                   "comment": 74, "visual": 84, "freshness": 96},
        "reason": "A great mechanism with no authoritative source yet and a niche framing "
                  "the channel has already covered from the AI angle.",
    },
    {
        "id": "hidecap",
        "title": "Proving a model can hide capabilities from its own safety tests",
        "kind": "emerging",
        "age_days": 1,
        "knowledge_type": "A system / cause-effect inside an evaluation",
        "evidence": ["Hacker News top story, 214 points, 'AI models can provably hide "
                     "arbitrary capabilities'"],
        "primary": [("arXiv preprint", "https://arxiv.org/abs/2610.13928")],
        "notes": "Primary paper exists and is retrievable.",
        "scores": {"hook": 82, "curiosity": 88, "retention": 78, "shareability": 80,
                   "comment": 82, "visual": 72, "freshness": 96},
        "reason": "Fascinating, but it needs probability theory to tell honestly, and it is "
                  "the third AI-adjacent video the channel would run in a week.",
    },
    {
        "id": "geothermal",
        "title": "First utility-scale enhanced geothermal plant goes live",
        "kind": "emerging",
        "age_days": 1,
        "knowledge_type": "A system / cause-effect (subsurface heat -> power)",
        "evidence": ["IEEE Spectrum 2026-10-12"],
        "primary": [("IEEE Spectrum article",
                     "https://spectrum.ieee.org/enhanced-geothermal")],
        "notes": "Energy technology, outside the Technology & Digital Life mechanism the "
                 "channel is scoped to: nothing happens inside a device, app or network.",
        "scores": {"hook": 78, "curiosity": 80, "retention": 76, "shareability": 74,
                   "comment": 70, "visual": 82, "freshness": 95},
        "reason": "Good physics, wrong niche: it is not something you use every day.",
    },
    {
        "id": "chip",
        "title": "Why a hardware spy chip fits inside a crypto wallet",
        "kind": "emerging",
        "age_days": 1,
        "knowledge_type": "Hidden parts of a product",
        "evidence": ["BleepingComputer 2026-10-12, 'Ledger confirms spy chip implant behind "
                     "wallet crypto thefts'"],
        "primary": [("Ledger statement",
                     "https://www.ledger.com/blog")],
        "notes": "Overlaps the published Exploded View territory and depends on a vendor's "
                 "own characterisation.",
        "scores": {"hook": 84, "curiosity": 86, "retention": 82, "shareability": 84,
                   "comment": 86, "visual": 90, "freshness": 94},
        "reason": "Vivid and visual, but the format territory is already used and the only "
                  "sourced account of the implant is the maker's.",
    },
    {
        "id": "margaret",
        "title": "Margaret Hamilton, the software engineer behind the Apollo guidance computer",
        "kind": "evergreen",
        "age_days": 900,
        "knowledge_type": "A person, not a mechanism",
        "evidence": ["Wikipedia most read, 10 Oct 2026, 162,739 views"],
        "primary": [("Wikipedia, Margaret Hamilton (software engineer)",
                     "https://en.wikipedia.org/wiki/Margaret_Hamilton_(software_engineer)")],
        "notes": "Huge real-world interest (Wikipedia most-read) but it is a biography, not "
                 "a mechanism, and section 4.2 requires one.",
        "scores": {"hook": 78, "curiosity": 82, "retention": 76, "shareability": 84,
                   "comment": 84, "visual": 66, "freshness": 40},
        "reason": "Popular, but the channel sells mechanisms, and a biography has no "
                  "mechanism to animate.",
    },
]

# Section 4.7: knowledge type -> format, from playbook 9.1, minus what is used.
FORMAT_MAP = {
    "A quantity changing over time": ("Data story / Two Lines", "Counter That Lies"),
    "A system / cause-effect": ("Systems Diagram", "Domino Chain"),
    "A process / sequence": ("Countdown / step explainer", "Terminal Explains"),
    "Hidden parts": ("Exploded View", "Interface Autopsy"),
    "A misconception": ("Myth->Mechanism", "The Wrong Graph"),
    "Scale": ("Zoom Out Ladder", "Fill the Jar"),
}


def overall(scores: dict) -> int:
    return round(sum(scores[k] * w for k, w in WEIGHTS.items()))


def knowledge_class(kt: str) -> str:
    for key in FORMAT_MAP:
        if kt.startswith(key.split(" / ")[0][:18]):
            return key
    return "A process / sequence"