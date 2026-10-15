# Arkad's Ledger

"Understand the money systems that control everyday life."

A fully native production pipeline for vertical, map-driven economics explainers.
No cloud services, no API keys, no stock assets. Everything is drawn, synthesised
and measured on the machine that runs it.

## What lives here

```
arkads-ledger/
  env.sh            environment only; exports variables, installs nothing
  setup.sh          idempotent, rootless bootstrap (safe to re-run)
  doctor.py         PASS/FAIL environment doctor; build.sh aborts on any FAIL
  build.sh          one command: doctor -> brain -> script -> render -> audio -> mux -> thumbnail -> QA
  README.md         this file
  assets/
    fonts/          Montserrat statics (fetched, gitignored)
    voices/         Piper en_US-ryan-high (fetched, gitignored)
    geo/            Natural Earth 10m shapefiles (fetched, gitignored)
  2026-10-13/       one day, one episode; all deliverables for this sample
    src/            theme, timeline, brain, geo, scenes, render, audio, qa, metadata
    video/          sample-final.mp4
    thumbnail/      sample-thumb.png (master) and sample-thumb.jpg (upload)
    audio/          narration, stems, master
```

`../videokit/` holds the channel-independent engine both channels import:
frame engine, text engine, motion vocabulary, vector components, Piper TTS,
caption alignment, voice QA, procedural audio, mixing, muxing and QA primitives.

## One command

```bash
wsl -d Ubuntu -- bash -lc "cd /mnt/c/\$USER/content-studio/arkads-ledger && source env.sh && bash build.sh"
```

From inside WSL:

```bash
cd arkads-ledger && source env.sh && bash build.sh
```

`build.sh` runs the doctor first and aborts on any failure. The single exception
is the Manim check: if Manim cannot render, charts and counters fall back to
pycairo with identical easing and the fallback is recorded in `qa-report.md`.

## Rebuilding just this episode

```bash
source env.sh
$PY 2026-10-13/src/brain/gather.py     # live sources -> candidates_raw.json
$PY 2026-10-13/src/brain/verify.py     # primary-source gate -> verification_log.json
$PY 2026-10-13/src/brain/select.py     # score, choose, -> facts.json + sources.md
$PY 2026-10-13/src/script_gen.py      # -> script.md + scenes_plan.json
$PY 2026-10-13/src/timeline.py         # TTS + voice QA + whisper -> timeline.json
$PY 2026-10-13/src/audio_mix.py        # SFX + music + loudnorm -> master_final.wav
$PY 2026-10-13/src/render.py           # frames -> sample-final.mp4
$PY 2026-10-13/src/thumbnail.py        # -> sample-thumb.png/.jpg
$PY 2026-10-13/src/metadata.py         # -> youtube-metadata.md/.json
$PY 2026-10-13/src/qa.py               # 13 gates -> qa-report.md
```

Steps are incremental and content-addressed: a re-synthesis that produces the
same bytes is reused from `.cache/tts/`, and an unchanged script does not
re-run the fetches.

## Making tomorrow's video

1. `mkdir -p 2026-10-14 && cp -r 2026-10-13/src 2026-10-14/`
2. Set `LEDGER_DAY_DIR=$PWD/2026-10-14` in the shell, or edit the default in
   `env.sh`.
3. Edit `2026-10-14/src/brain/gather.py` only if you want to seed different
   evergreen questions. The exclusion list lives there too, so add anything
   published since to `EXCLUSIONS` or the brain will happily reuse it.
4. Run the commands above with the new day directory.
5. Do not hand-edit `timeline.json`: it is generated from the measured TTS.
   If a sentence is wrong, change `script_gen.py` and re-run from step 4.

`timeline.py` is the single source of time. The renderer and the audio engine
both read it, so the picture and the sound cannot drift.

## Editorial rules this pipeline enforces in code

- Every number on screen comes from `facts.json`, written by the same function
  that draws it, and is asserted before use.
- Countries appear only as evidence for a universal mechanism. No jurisdiction-
  specific advice, no buy/sell/hold, no stock picks, no return promises.
- The exclusion list in `brain/gather.py` blocks already-published topics.
- Illustrative figures are tagged `kind: illustrative` in `facts.json` and
  labelled EXAMPLE on screen.
- Safe zones, type sizes and the palette live only in `theme.py`.

## Adding a channel

`arkads-ledger` and `abitinside` share `videokit/`. A third channel needs only a
directory with `env.sh`, `setup.sh`, `doctor.py`, `build.sh` and its own
`src/theme.py`, `src/timeline.py`, `src/scenes.py` and `src/brain/`. Everything
in between is already in the shared package.

The one thing to keep straight: `abitinside/layout/` is that channel's own
constraint solver and is deliberately NOT shared. `arkads-ledger` uses its own
theme and its own map engine, and `abitinside/layout/layout_spec.yaml` is never
edited from here.
