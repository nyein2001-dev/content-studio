# Scene spec for the content bot

Output components and text only. Never output x, y, width, height, or a font size.

```yaml
id: scene_id
profile: portrait
duration_s: 3.0
brand: "A Bit Inside"
headline: "LINE ONE\nLINE TWO"
caption: "eight words or fewer"
footnote: "ILLUSTRATIVE"   # omit when there is no badge
stage:
  - id: block
    type: card
    title: "HEADING"
    body: "sub-line"
```

Limits: title 28 characters per line, 2 lines; chip 18 characters; card heading 24; card sub-line 34; caption 8 words; 7 stage elements; 2 chips per row; 4 rows.

`type` is one of `chip_row`, `card`, `stat`, `line_chart`, `timeline`, `hub_and_spoke`, `severity_meter`, `callout`.

## By morning, fifty degrees (HERO_CHART)

Chart, then a chip row of at most two chips per row, then the notice card on its own row.

## Most were already unsupported (TIMELINE)

`timeline` with AUG 2025 below the axis and OCT 2026 above it. Cards sit under the axis, not on the ticks.

## A password made of dates (CARD_STACK)

LOGIN ACCEPTED and CODE OF THE DAY are separate cards. The severity meter is its own row. `footnote: ILLUSTRATIVE` puts the badge in the BADGE zone.

## A web page in the store (HUB_AND_SPOKE_DIAGRAM)

Cards connect with `connectors`. The sentence sits in the card body so the line does not cross it.

## One box behind the cases (HUB_AND_SPOKE_DIAGRAM)

`hub_and_spoke` places PROBES, TARGET, and DEFROST in a label row, not on the case icons.

## Map callout (MAP_CALLOUT)

A single `callout` card. No coordinates.
