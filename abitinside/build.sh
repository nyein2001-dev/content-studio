#!/usr/bin/env bash
# =====================================================================
#  A Bit Inside - one command rebuilds the whole day's video.
#
#      bash abitinside/build.sh [YYYY-MM-DD]
#
#  Steps, in order, aborting on the first failure:
#    0  environment doctor            (abort on any FAIL)
#    1  topic research + selection    -> brain-report.md
#    2  script from facts.json        -> scenes_plan.json, script.md
#    3  narration (Piper)             -> tts_sentences.json, audio/narration.wav
#    4  word alignment (whisper)      -> align.json
#    5  timeline from measured audio  -> timeline.json (the single source of truth)
#    6  audio engine                  -> cue-sheet.txt, audio/*.wav
#    7  render + mux                  -> video/sample-final.mp4 (and the no-narration cut)
#    8  delivery QA                   -> qa-report.md, contact-sheet.png
# =====================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "$HERE/env.sh"

DAY="${1:-${ABIT_DAY_DIR##*/}}"
DAY_DIR="$ABIT_HOME/$DAY"
SRC="$DAY_DIR/src"
PY_BIN="$PY"

step() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
fail() { printf '\033[1;31mBUILD FAILED: %s\033[0m\n' "$*" >&2; exit 1; }

[ -d "$SRC" ] || fail "no source directory at $SRC (expected abitinside/$DAY/src)"
cd "$SRC" || fail "cannot enter $SRC"

# ---------------------------------------------------------------- 0
step "0/9  environment doctor"
"$PY_BIN" "$HERE/doctor.py" || fail "doctor.py reported a FAIL - run setup.sh first"

# ---------------------------------------------------------------- 1
step "1/9  social content brain"
"$PY_BIN" "$SRC/brain/gather.py" || fail "candidate gathering failed"
"$PY_BIN" "$SRC/brain/verify.py" || fail "source verification failed"
"$PY_BIN" "$SRC/brain/select.py" || fail "winner selection failed"

# ---------------------------------------------------------------- 2
step "2/9  script"
"$PY_BIN" "$SRC/script_gen.py" || fail "script validation failed"

# ---------------------------------------------------------------- 3
step "3/9  narration (Piper, offline)"
"$PY_BIN" "$SRC/tts.py" || fail "narration synthesis failed"

# ---------------------------------------------------------------- 4
step "4/9  word alignment (faster-whisper, offline)"
"$PY_BIN" "$SRC/align.py" || fail "word alignment failed"

# ---------------------------------------------------------------- 5
step "5/9  timeline"
"$PY_BIN" "$SRC/timeline.py" || fail "timeline generation failed"
"$PY_BIN" "$SRC/script_gen.py" >/dev/null || true   # rewrite script.md with real stamps

# ---------------------------------------------------------------- 6
step "6/9  audio engine"
"$PY_BIN" "$SRC/audio/mix.py" || fail "audio mix failed"

# ---------------------------------------------------------------- 7
step "7/9  render and mux"
"$PY_BIN" "$SRC/render.py" || fail "render or mux failed"

# ---------------------------------------------------------------- 8
step "8/9  delivery QA"
"$PY_BIN" "$SRC/qa.py" || fail "a QA gate failed - see qa-report.md"

# ---------------------------------------------------------------- 9
step "9/9  stamp the measured numbers into the YouTube package"
"$PY_BIN" "$SRC/stamp_metadata.py" || fail "could not stamp youtube-metadata"

printf '\n\033[1;32m==> BUILD COMPLETE\033[0m\n'
printf '    video/sample-final.mp4\n'
printf '    video/sample-music-sfx-only.mp4\n'
printf '    script.md, facts.json, sources.md, cue-sheet.txt\n'
printf '    qa-report.md, contact-sheet.png, brain-report.md\n'
printf '\n\033[1;33mA human must still watch the mp4 once with sound on and once muted.\033[0m\n'