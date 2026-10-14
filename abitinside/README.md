# A Bit Inside - production pipeline

Everything is produced natively on this machine: **Python + pycairo**, numpy/scipy, FFmpeg,
procedurally synthesised audio, and a local neural voice. No cloud service, no API key, no
stock footage, music or image, and no third-party logo or screenshot anywhere in the output.

```
abitinside/
  setup.sh          one-time, idempotent, ROOTLESS bootstrap
  doctor.py         24 PASS/FAIL checks; build.sh aborts if any FAIL
  env.sh            the single place where PATH / library paths are set
  build.sh          setup check -> research -> script -> voice -> mix -> render -> QA
  .venv/            CPython 3.11 virtualenv            (gitignored, rebuilt by setup.sh)
  tools/            ffmpeg/ (static), cdeps/, toolchain/, micromamba/   (gitignored)
  assets/fonts/     Poppins + JetBrains Mono TTFs      (gitignored, re-downloaded)
  assets/voices/    Piper en_US-ryan-high             (gitignored, re-downloaded)
  .cache/           whisper model, font cache, QA scratch                (gitignored)
  2026-10-13/       one day's output, built from scratch
```

---

## 1. First run

```bash
wsl -d Ubuntu
cd /mnt/c/Users/dell/AnimationContentStudio/ABitInside
bash abitinside/setup.sh          # ~10 min the very first time, seconds afterwards
python abitinside/doctor.py       # must print "All 24 checks passed"
```

`setup.sh` is **rootless on purpose** - this machine's WSL `sudo` needs a password, so nothing
is installed system-wide. Everything lands inside `abitinside/`:

| need | how | where |
|---|---|---|
| CPython 3.11 | `uv` + python-build-standalone | `~/.local/share/uv` |
| virtualenv | `uv venv` | `.venv/` |
| cairo/pango headers | rootless `micromamba` from conda-forge | `tools/cdeps/` |
| C compiler (pycairo has no wheel) | rootless `micromamba` gcc | `tools/toolchain/` |
| FFmpeg >= 6 | johnvansickle static build | `tools/ffmpeg/` |
| fonts | Google Fonts GitHub | `assets/fonts/` |
| voice | `rhasspy/piper-voices` | `assets/voices/` |
| word timestamps | `faster-whisper base.en` | `.cache/huggingface/` |

Re-running `setup.sh` is safe and fast: every step checks for what it already produced.

---

## 2. Rebuilding a day

```bash
bash abitinside/build.sh 2026-10-13
```

Eight steps, each aborting the build on failure:

| step | script | produces |
|---|---|---|
| 0 | `doctor.py` | environment verified, or the build stops here |
| 1 | `src/brain/gather.py`, `verify.py`, `select.py` | `candidates_raw.json`, `verification_log.json`, `brain-report.md` |
| 2 | `src/script_gen.py` | `scenes_plan.json`, `script.md` |
| 3 | `src/tts.py` | `tts_sentences.json`, `audio/narration.wav` |
| 4 | `src/align.py` | `align.json` (word-level caption timings) |
| 5 | `src/timeline.py` | `timeline.json` - **the single source of truth for time** |
| 6 | `src/audio/mix.py` | `cue-sheet.txt`, `audio/*.wav` |
| 7 | `src/render.py`, `src/mux.py` | `video/sample-final.mp4`, `video/sample-music-sfx-only.mp4` |
| 8 | `src/qa.py` | `qa-report.md`, `contact-sheet.png` |

Scene lengths are **measured, never estimated**: step 3 measures each sentence with Piper, and
step 5 derives every scene, beat and caption frame from those measurements. Change a sentence
and the whole timeline reflows around it.

### Useful overrides

```bash
ABIT_WORKERS=1 bash abitinside/build.sh 2026-10-13   # single-core render
```

---

## 3. Making tomorrow's video

1. **Research.** `brain/gather.py` pulls Hacker News (top + best), Wikipedia top-viewed and
   most-read, and fifteen RSS feeds; it writes everything with URLs and retrieval times to
   `candidates_raw.json`. Nothing is invented at any point.
2. **Choose.** Edit `src/brain/candidates.py`: add candidates, score them, and set
   `rejected` with a reason for anything that trips the exclusion list. `verify.py` then
   re-fetches every primary source and records the real HTTP status;
   `select.py` applies the winner rule and the format rule and writes `brain-report.md`.
3. **Facts first, script second.** Write `facts.json`. Every number the video will ever say or
   show goes in there with a source URL and a `source_wording` paraphrase, or a `derivation`
   that names the code computing it. Mark anything invented as `"kind": "illustrative"`.
4. **Script.** Edit `SCENES` in `src/script_gen.py`: headline lines, spoken sentences,
   illustration key, beats. It validates the rules for you - 240-330 words, sentences under 22
   words, no like/follow request, headline limits - and refuses to write a script that breaks
   them.
5. **Draw.** Add a function in `src/render/scenes.py` and register it in the `SCENES` map at the
   bottom. Scenes may only read numbers through `v(fact_id)`, which reads `facts.json`.
6. **Build.** `bash abitinside/build.sh <new-date>`. The QA gates are the judge; if a gate
   fails, the build fails and `qa-report.md` names the measurement.

Copy a finished day and change the date to start:

```bash
cp -r abitinside/2026-10-13 abitinside/2026-10-14
bash abitinside/build.sh 2026-10-14
```

---

## 4. House rules the code enforces

| rule | enforced by |
|---|---|
| 1080x1920, 30 fps CFR, never upscaled | `render/engine.py`, QA gate 1 |
| all content inside x 120-960, nothing below y 1610 | a hard clip in `compose_frame`, QA gate 3 |
| no dead frame after a scene cut | beat 0 lands on the cut, QA gate 3h |
| headline and captions centred on x=540 | measured per string, QA gate 3f/3g |
| no glyph the font does not have | fontconfig loads only our four TTFs, QA gate 4 |
| every number traces to `facts.json` | QA gate 6a |
| every source URL answered 200 in this run | QA gate 6b |
| -14 LUFS and TP <= -1.5 dBTP together | soft limiter + measured gain, QA gate 2 |
| last frame equals first frame | 4-frame narration lead-in, QA gate 9d |

---

## 5. Hardware note

This box is an **Intel i5-6200U at 2.30 GHz with 2 cores and 3.9 GB of RAM** - roughly a fifth
of the 8-core machine the brief assumed. Measured on it:

- full render: **5-13 minutes** for 3,299 frames depending on what else is running
- narration (Piper): ~4.5 min · alignment (Whisper base.en): ~2.5 min · audio mix: ~1.7 min
- whole pipeline end to end: roughly **25-30 minutes**

The 25-minute figure is not met by the complete pipeline, and the reason is the CPU, not the
code. Everything is parallelised across both cores and the expensive layers are cached.

---

## 6. What still needs a human

The automated gates measure decoded frames and audio. They cannot tell you whether the video
**feels** right.

> **Watch `video/sample-final.mp4` once with sound on and once muted, on a phone, before
> uploading it.** An AI editor cannot watch video.

Also worth a human eye: whether the spoken pacing lands well in the ear rather than only on
the waveform, and whether the animation reads as calm rather than merely as fast.
