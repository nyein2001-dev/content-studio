# Layout contract

Drop this into the content brief for any new video. The engine will not repair a scene that breaks it. Fix the DSL until `make gate-showcase` (or `python -m layout gate --video <file>`) exits 0.

The words in the DSL are authoritative. The solver may wrap, shrink to a floor, switch to a declared `alternate`, or split a scene marked `splittable`. It will not truncate, ellipsize, hyphenate, or rewrite a word.

## Density

Per scene, on the portrait canvas:

- duration at least 2.5 seconds
- at most 6 stage components
- at most 4 chips, counting hub spokes
- at most 1 cursor overlay
- at most 3 text blocks besides the headline and the caption
- headline at most 2 lines, and it must fit at 66 px
- caption at most 2 lines inside a 160 px band, so a long caption will be set nearer 52 px than 72 px
- stage art must fill at least 45% of the stage height; aim for 60%

Length limits follow the type floors. A chip is one line at 28 px or larger. A card title is at least 36 px. Body is at least 30 px. A counter is monospace and needs `max_value` set to the widest string it can show.

## Fields the DSL must not contain

`x`, `y`, `w`, `h`, `font_size`, `size`, `color`, `colour`, `hex`. Color comes from the theme. Position comes from the solver.

`alternate: vertical` lets a chip row become a column. `alternate: stack` lets a comparison become two stacked cards. `splittable: true` is allowed only when cutting the scene in half still leaves each beat at 2.5 seconds or more. `optional: true` on a timeline tick lets that label drop instead of colliding.

## Schema

A scene is a JSON object validated by `layout/schema/scene.schema.json`. Required: `id`, `profile` (`portrait`, `landscape`, or `square`), `duration_s`, `brand`, `headline`, `caption`, `stage`. Optional: `footnote`, `splittable`, `overlay`, `connectors`.

Stage `type` is one of: `chip_row`, `card`, `stat`, `line_chart`, `bar_chart`, `timeline`, `flow`, `hub_and_spoke`, `code_panel`, `severity_meter`, `callout`, `checklist`, `comparison`.

## Example

```yaml
id: hero_chart
profile: portrait
duration_s: 3.0
splittable: false
brand: "A Bit Inside"
headline: "FIFTY DEGREES"
caption: "by morning"
footnote: "ILLUSTRATIVE"
stage:
  - id: chart
    type: line_chart
    title: "CASE TEMPERATURE"
    series: [4, 4, 6, 18, 40, 50]
    y_labels: ["0", "25", "50"]
    x_labels: ["DUSK", "DAWN"]
  - id: chips
    type: chip_row
    labels: ["AK-SM", "AK-SC"]
    alternate: vertical
```

A video file lists scene paths:

```yaml
title: Layout showcase
profile: portrait
scenes:
  - hero_chart.yaml
```

If the gate prints a rule id, the remedy in that line is the edit. Do not move a number in Python to make the picture fit.
