#!/usr/bin/env python3
"""YouTube package: human-readable markdown plus the machine-readable json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3]))
import theme as T  # noqa: E402
from videokit import qa_core as Q  # noqa: E402

DAY = HERE.parent
F = json.loads((DAY / "facts.json").read_text(encoding="utf-8"))
YEAR = F["year"]

TITLE = "Why one dollar buys two different lives"
DESCRIPTION = (
    "One American dollar buys about eight dollars worth of life in Nigeria. "
    "This short maps the price level ratio, the number that shows what your "
    "money actually buys once prices are local.\n\n"
    f"The World Bank measures the spread as a price level ratio. The United States "
    f"is the reference at {F['facts']['price_level_ratio_USA']['value']:.3f}. The "
    f"United Kingdom is {F['facts']['price_level_ratio_GBR']['value']:.2f}, Germany "
    f"{F['facts']['price_level_ratio_DEU']['value']:.2f}, Japan "
    f"{F['facts']['price_level_ratio_JPN']['value']:.2f}, Mexico "
    f"{F['facts']['price_level_ratio_MEX']['value']:.2f}, India "
    f"{F['facts']['price_level_ratio_IND']['value']:.2f} and Nigeria "
    f"{F['facts']['price_level_ratio_NGA']['value']:.3f}. That is a "
    f"{F['facts']['ratio_ratio']['value']:.1f} times gap between the highest and "
    f"lowest economy in this set. Figures are real published data for {YEAR}, the "
    f"latest available release. The two numbers are both correct and answer "
    f"different questions: an exchange rate is a trade quote, a price level is a "
    f"shopping list.\n\n"
    "Sources:\n"
    f"World Bank, World Development Indicators, GDP per capita (current US$), "
    f"NY.GDP.PCAP.CD, {YEAR}: https://api.worldbank.org/v2/country/all/indicator/"
    f"NY.GDP.PCAP.CD?format=json&date=2021:2025\n"
    f"World Bank, World Development Indicators, GDP per capita, PPP "
    f"(constant 2021 international $), NY.GDP.PCAP.PP.CD, {YEAR}: "
    f"https://api.worldbank.org/v2/country/all/indicator/NY.GDP.PCAP.PP.CD"
    f"?format=json&date=2021:2025\n"
    "Map boundaries: Natural Earth 10m (public domain).\n\n"
    "Illustrative values and shapes are labelled on screen in the video.\n"
    "Educational content, not financial advice.\n\n"
    "#economics #money #purchasingpower #ArkadsLedger #Shorts"
)
TAGS = ["purchasing power parity", "price level ratio", "inflation explained",
        "cost of living by country", "exchange rate", "world bank data",
        "money explained", "map of money", "personal finance basics",
        "global economics", "arkads ledger"]

PINNED = (
    "Sources and data dates:\n"
    f"- World Bank, World Development Indicators, NY.GDP.PCAP.CD (GDP per capita, "
    f"current US$), data year {YEAR}.\n"
    f"- World Bank, World Development Indicators, NY.GDP.PCAP.PP.CD (GDP per "
    f"capita, PPP), data year {YEAR}.\n"
    "- Map boundaries: Natural Earth 10m.\n\n"
    "The price level ratio is computed in the video as nominal GDP per capita "
    "divided by PPP GDP per capita. Every figure on screen comes from those two "
    "published series; nothing is estimated. Any illustrative value is labelled "
    "on screen.\n\n"
    "Educational content, not financial advice."
)

CHECKLIST = [
    "Signed in as the Arkad's Ledger channel, never another brand.",
    "Custom cover uploaded from thumbnail/sample-thumb.jpg (1080x1920, under 2 MB).",
    "Title, description, hashtags and the pinned comment pasted from this file.",
    "Category Education, language English, audience not made for kids, visibility "
    "Public, comments on.",
    "Altered or synthetic content disclosure set as recorded below.",
    "Watched once on a phone with sound and once muted before publishing.",
]


def main() -> int:
    urls = sorted({v["url"] for v in F["facts"].values() if v.get("url")})
    md = [
        "# YouTube upload package - Map of Money, Episode 2", "",
        "## Title", "", f"`{TITLE}`", "",
        f"({len(TITLE)} characters. Sentence case, primary keyword early, no all-caps, no hashtags.)",
        "", "## Description", "", "```", DESCRIPTION, "```", "",
        f"({len(DESCRIPTION.encode('utf-8'))} bytes, limit 4000.)", "",
        "## Tags", "", "```", ", ".join(TAGS), "```", "",
        f"({len(', '.join(TAGS))} characters, limit 400.)", "",
        "## Pinned comment", "", "```", PINNED, "```", "",
        "## Upload settings", "",
        "| Setting | Value |", "|---|---|",
        "| Category | Education |",
        "| Language | English |",
        "| Audience | No, not made for kids |",
        "| Visibility | Public |",
        "| Comments | On |",
        "| Schedule | Do not schedule. Posting is done by a human. |",
        "| Altered / synthetic content disclosure | **Yes** - select the option that "
        "discloses synthetic or altered content. |", "",
        "### Disclosure note", "",
        "YouTube's policy asks creators to disclose realistic altered or synthetic "
        "content. This video is fully original vector animation with a locally "
        "generated neural narrator, so it is disclosed as synthetic content. No human "
        "narrator is implied anywhere in this package. Verify the exact wording in "
        "Studio at upload time, because YouTube updates this control. Policy reference: "
        "https://support.google.com/youtube/answer/14328491", "",
        "## Pre-publish checklist", "",
    ] + [f"- [ ] {c}" for c in CHECKLIST] + [
        "", "## Source URLs used in this build", "",
    ] + [f"- {u}" for u in urls] + [""]

    (DAY / "youtube-metadata.md").write_text("\n".join(md), encoding="utf-8")
    (DAY / "youtube-metadata.json").write_text(json.dumps({
        "brand": T.BRAND, "series": T.SERIES, "episode": T.EPISODE,
        "title": TITLE, "title_length": len(TITLE),
        "description": DESCRIPTION,
        "description_bytes": len(DESCRIPTION.encode("utf-8")),
        "hashtags": ["#economics", "#money", "#purchasingpower",
                     "#ArkadsLedger", "#Shorts"],
        "tags": TAGS, "tags_length": len(", ".join(TAGS)),
        "pinned_comment": PINNED,
        "settings": {"category": "Education", "language": "English",
                     "made_for_kids": False, "visibility": "Public",
                     "comments": True, "scheduled": False,
                     "altered_or_synthetic_disclosure": True,
                     "disclosure_reason": "fully original vector animation with a "
                                          "locally generated neural narrator",
                     "disclosure_policy_url":
                         "https://support.google.com/youtube/answer/14328491"},
        "checklist": CHECKLIST,
        "data_year": YEAR,
        "sources": urls,
        "disclaimer": T.DISCLAIMER,
    }, indent=2), encoding="utf-8")
    print(f"title {len(TITLE)} chars, description {len(DESCRIPTION.encode())} bytes, "
          f"tags {len(', '.join(TAGS))} chars")
    print(f"-> {DAY / 'youtube-metadata.md'}")
    print(f"-> {DAY / 'youtube-metadata.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
