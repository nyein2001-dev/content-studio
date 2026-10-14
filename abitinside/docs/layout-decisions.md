# Layout decisions

Locked choices for the safe-zone engine. The stricter option is the one below.

## Package and spec

New code is `abitinside/layout/`. `layout/layout_spec.yaml` at semver 1.0.0 is the only place a layout number may live. The loader fails if the YAML does not match the JSON Schema. `pipeline/layout.py` stays the legacy collision helper. New code does not read its geometry, and the existing pipeline tests keep their expectations.

## Canvas

Profiles are portrait 1080×1920 (default), landscape 1920×1080, and square 1080×1080. Zone edges scale from the reference pixels and snap to the 8 px grid. Font floors do not scale. A profile that cannot fit a floor raises `LayoutError`. Templates are required to pass on portrait.

The stage column is the rail-safe width for the full stage height. A component that is legal above y 1000 must still be legal when the stack carries it down into the rail. Caption centering uses the caption safe region, not x 540.

## Brand and fonts

Colors and font file paths come from `2026-10-13/src/theme.py`. The renderer refuses any hex that is not one of those tokens. Font sizes and coordinates in `theme.py` are legacy-only.

`assets/fonts.conf.tpl` is not edited. Its catch-all assigns Poppins Bold to a generic Poppins request, and a later match overwrites the medium-weight file assignment, so `fc-match` cannot be asked to prove SemiBold without changing the file the sample renderer uses. The new engine rasterizes glyphs from the TTF path with Pillow and composites them onto cairo. fontTools checks the name table and the OS/2 weight class (bold 700, semibold 600, regular 400, mono 400). `fc-match` must still resolve bold and JetBrains Mono to the bundled filenames, and a generic Poppins lookup must stay inside `assets/fonts/`. Any other file is a failed build.

Stroke width is 3, the brand stroke. The headline underline is the 8 px grid token.

## Drawing

pycairo only. Charts are cairo paths. The renderer entry point accepts a `PlacedScene` and has no coordinate parameters. Source lint allows cairo calls only in `layout/render.py`, `layout/debug.py`, `layout/metrics.py`, and `layout/legacy.py`.

## Sample episode

`2026-10-13/` is authored as scene YAML under `scenes/` and rendered by the layout engine. `legacy_roots` is empty. A scene that still sets `legacy` fails with `LEGACY-UNMIGRATED` and is not published.

`pipeline/export.py` `remember()` and `2026-10-13/src/stamp_metadata.py` call `assert_certified` before upload metadata is written. The sample can still render. It can no longer be stamped as a publishable package.

## Motion, gaps, and fill

Shared slots are sequential. Default motion is an opacity fade over `enter_frames`. Scale stays 1.0 unless declared, and cannot exceed 1.05.

Sibling gap is checked for every pair of top-level nodes. Chips in a row use 16 px. Other siblings use 24 px. Glow may overlap glow and may not cover text. A cursor is not part of the stage stack, so a corner pointer does not count as a hole in the diagram.

If stage fill is under 60%, the solver adds decorative bars (40 px, 24 px apart) until the stack reaches the target or it cannot do so without leaving the stage. Fill under 45% fails. Between 45% and 60% warns.

## Publish and performance

Renders write `out/draft/`. Promotion to `out/publish/` is an atomic directory replace after lint, static, swept, pixel, and parity all pass. The certificate stores the sha256 of the mp4, the spec version, the validator version, per-check results, and a UTC timestamp. Tests ignore the timestamp.

The validator path for a 3-minute 30 fps timeline is budgeted at under 5 minutes on this 2-core machine, using cached glyph masks and `os.cpu_count()` workers. The production `preset slow` encode is already 5–13 minutes and is not part of that budget. The showcase uses the episode encoder flags: CRF 16, preset slow, tune animation, high profile, level 4.2, yuv420p, bt709. The perf fixture encodes only its parity sample, with `veryfast`.

A settled hero frame encoded with those flags measures about 39.6 dB. Busier showcase frames measure 35.9–36.9 dB. The loss is yuv420p chroma on the cyan and yellow strokes, at the same CRF the episode already uses. The parity floor is 35. It still rejects a broken color round trip. It is stored as `rules.psnr_min`.

Certificate and showcase mp4 files are gitignored under `out/`. The showcase contact sheet is `examples/layout_showcase/contact-sheet.png`. The sample rejection summary is `tests/fixtures/layout/sample_rejection/layout_report.json`.

## Fuzz

The stress seed is `20261014`. A solved scene with a hard violation fails the test. A `LayoutError` is a clean refusal and passes. Other exceptions fail the test.

## Debug colors

Zone and violation overlays use theme tokens: cyan for zones, coral for keepouts, green for element boxes, yellow for ink. There is no second palette.
