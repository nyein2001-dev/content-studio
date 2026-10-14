# Layout rules

Numbers live only in `abitinside/layout/layout_spec.yaml`. Scenes name components and text. The solver places them. The text engine measures and draws every glyph.

## Zones

Canvas 1080x1920. Safe x is 120 to 960.

| Zone | y | What may be there |
|---|---|---|
| PLATFORM_TOP | 0 to 180 | background only |
| BRAND | 200 to 290 | the A Bit Inside tag |
| TITLE | 330 to 540 | at most 2 lines, plus the accent underline |
| BADGE | 600 to 644 | ILLUSTRATIVE or SIMULATION, right-aligned |
| STAGE | 668 to 1380 | diagrams, charts, cards, chips |
| SUBTITLE | 1420 to 1580 | at most 2 lines |
| PLATFORM_BOTTOM | 1580 to 1920 | background only |

Spacing: 8 px grid, 24 px container padding, 24 px between siblings, 16 px between text and a non-owning edge. Glow, shadow, and stroke are inside the box.

## Type

| Role | Preferred | Floor | Lines |
|---|---|---|---|
| title | 72 | 56 | 2 |
| stage | 36 | 30 | 2 |
| chip | 34 | 28 | 1 |
| subtitle | 56 | 44 | 2 |
| badge | 26 | 24 | 1 |

Nothing is drawn below its floor. Fonts are the bundled Poppins and JetBrains Mono files. A missing file fails the build.

## Content limits

Title 28 characters per line and 2 lines. Chip label 18 characters. Card heading 24. Card sub-line 34. Subtitle 8 words and 2 lines. At most 7 stage elements visible at once, 2 chips per row, 4 rows.

## Rules

| Id | Fails when |
|---|---|
| R01 | A content element leaves the safe area or its zone |
| R02 | Anything except background enters a platform keep-out |
| R03 | Text leaves its container or the 16 px padding |
| R04 | Two text boxes overlap |
| R05 | Text crosses a shape it does not belong to |
| R06 | Shapes overlap outside the allowed layer pairs |
| R07 | Siblings are closer than 24 px |
| R08 | A connector crosses text inflated by 12 px |
| R09 | Text is under the type floor or over its line cap |
| R10 | Ink is more than 2 px off the container center |
| R11 | Two elements share a slot at overlapping times |
| R12 | More than 7 stage elements are visible |
| R13 | Text contrast is under 4.5:1 |
| R14 | Text is on screen for less than max(1.2 s, words / 3) |
| R15 | A content limit is exceeded |
| R16 | The empty space above and below the stage stack differs by more than 96 px |

Auto-fix, in order: shrink toward the floor, reflow chips onto another row, restack a slot. Each fix is a warning. Anything else is an error. The engine does not truncate.

## Components

BrandTag, Title, Badge (a boolean; the template places it), Subtitle, Chip, ChipRow, Card, NoticeBox, Stat, TimelineAxis, Chart, ConnectorGraph, IconRow, Pointer, Divider.

## Templates

Each scene picks one: HERO_CHART, STAT_STACK, TIMELINE, HUB_AND_SPOKE_DIAGRAM, CARD_STACK, CHIP_GRID_WITH_NOTICE, MAP_CALLOUT.

## Adding a component or template

1. Add the component as data. Do not add x or y.
2. Give it one slot rectangle inside STAGE, stacked with a 24 px gap and centered as a group.
3. Measure text only through `layout/text.py`.
4. Add a negative test and a positive test.
5. Run `python -m layout validate` and `python -m layout qa`.
6. If a rule fails, shorten the content or change the template. Do not change a threshold.
