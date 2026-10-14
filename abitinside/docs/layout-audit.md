# Layout audit

Discovery of the animated-video pipeline before the safe-zone engine. The zone spec wins for every new video. The 2026-10-13 episode is frozen and is the negative fixture.

## How a video is built

Shared code lives in `abitinside/pipeline/`. One episode lives in `abitinside/2026-10-13/`. `build.sh` runs doctor, the topic brain, `src/script_gen.py`, `pipeline/tts.py`, `pipeline/captions.py`, `src/timeline.py`, `src/audio/mix.py`, `src/render.py`, `src/qa.py`, and `src/stamp_metadata.py`.

There is no Grok client and no prompt file. `src/brain/` only fetches and scores topics. Spoken scenes are the `SCENES` list in `2026-10-13/src/script_gen.py`. Drawing is a Python function per scene in `2026-10-13/src/render/scenes.py`, registered in the `SCENES` map. Numbers on screen come from `facts.json` through `v()`. Positions and font sizes are literals or `theme.py` constants.

`pipeline/layout.py` only tests whether two boxes intersect. The renderer never imports it.

## Render loop

`src/render/engine.py` paints with pycairo at the theme canvas, 30 fps. Workers rasterize raw RGB into FFmpeg (`libx264`, CRF 16, preset `slow`, yuv420p). `src/mux.py` muxes AAC and names the file from the title via `pipeline/export.py`. Output stays in `2026-10-13/video/`. Nothing promotes into a certified publish directory.

`compose_frame` draws a cached background, clips scene art to x 120–960 and y 520–1462, then draws the headline, one caption line, and the wordmark outside that clip. Matplotlib and Manim are not on this path.

Text goes through `engine.Text`: FontConfig family name, `set_font_size`, `show_text`. `text_extents` advance is what the episode uses for centering. The new engine uses ink bearings instead, and refuses a font that is not one of the four bundled files.

## Constants that conflict with the zone spec

Episode theme and `pipeline/config.py` (and a third copy inside `src/qa.py`):

| Constant | Episode | Zone spec |
|---|---|---|
| Canvas | 1080×1920, 30 fps | Same default, plus 1920×1080 and 1080×1080 profiles |
| Side inset | x 120–960 (width 840) | Margin 72, content width 936, then the right rail |
| Wordmark | y 250, 30 px | BRAND y 200–300 |
| Headline | top 364, pitch 73, underline y 512, 66 px, max 2 lines | HEADLINE y 320–560, floor 64, max 2 lines |
| Illustration | y 560–1420, clip to y 1462 | STAGE y 600–1340 |
| Caption | center y 1505, 72 px, floor y 1610 | CAPTION y 1440–1600, floor 52, and nothing below y 1600 |
| Right rail | none | x 944–1080, y 1000–1600, decorative background only |
| Minimum type | `SIZE_MIN` 34, not read by QA | headline 64, caption 52, card title 36, body 30, chip 28, footnote 26, mono 32 |

QA gate 3 still checks the old rect. It does not know about the rail, ink centering, connectors, or the 45 percent stage fill. Those gates stay as they are so the episode's own QA script is unchanged. They are not the publish gate.

Preferred sizes that already clear a floor (headline 66, caption 72, label 36, wordmark 30) are recorded in `layout/layout_spec.yaml` as preferred sizes. A 72 px caption cannot take two lines inside a 160 px caption band, so the fit ladder shrinks toward the 52 px floor. That is the spec winning, not a change to the episode pictures.

## Where the sample breaks the spec

These are the defects the legacy probe and the static rules are expected to report. Scene sources are not edited.

- D1, LR-01 / LR-03 / LR-04 / LR-05. `chip()` in `components.py` starts the label at the chip's horizontal center, so "COPELAND XWEB" and "DIXELL XWEB" in `the_reveal` run out of a fixed 390 px chip and into the neighbor and the right rail.
- D2, LR-02. The second chip row (y 1188, height 64) intersects the prosecutor card at y 1240. Pills in `controller` sit on the case tops.
- D3, LR-03. "built from the box's own date" is drawn near the bottom edge of the code card in `the_flaw`.
- D4, LR-08. In `legacy`, "AUG 2025" starts on the tick x, and "OCT 2026" is placed so a wide label runs past the axis end.
- D5, LR-09. `illustrative()` draws "ILLUSTRATIVE" at a free y (`ILLU_Y` 1378, or under a card) instead of the footnote band or an interior corner anchor.
- D6, LR-06 / LR-07. Dashed spokes in `controller` cross the sentence under the box. Pills overlap the cases they name.
- D7, LR-10. Several scenes leave a tall empty band in the stage and pack the remaining art into one cluster.
- D8, LR-01 / LR-14. The scene clip extends to y 1462, which is inside the caption band. The hook shockwave radius grows to hundreds of pixels and crosses the caption band and the bottom keepout. Caption entrance offsets are not reserved inside the caption safe rect.

## Wiring that had to change

`pipeline/export.py` `remember()` and `2026-10-13/src/stamp_metadata.py` now refuse to write an upload package unless `layout_certificate.json` matches the file hash. Scene functions, theme numbers, the script, the timeline, and the existing mp4 are not modified. A rebuild can still render the episode; it cannot stamp that file as publishable.

`setup.sh` gains the two pinned libraries the new package imports (`PyYAML`, `jsonschema`). Fonts stay downloaded by `setup.sh` and gitignored.

## What new videos use

Authors write scene DSL. `layout/layout_spec.yaml` is the only layout number source. The solver measures glyphs, places slots, and the cairo boundary draws placed rectangles only. Publish copies `out/draft/` to `out/publish/` with a certificate after every validator passes.
