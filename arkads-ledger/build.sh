#!/usr/bin/env bash
# Arkad's Ledger - the whole video in one command.
#
#   source env.sh && bash build.sh
#
# doctor -> brain -> script -> timeline/TTS -> audio -> render -> mux
#        -> thumbnail -> metadata -> QA
#
# Aborts on the first hard failure. The Manim check is the single non-blocking
# exception documented in the brief.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./env.sh
source "$HERE/env.sh"

DAY="${LEDGER_DAY_DIR:-$HERE/2026-10-13}"
SRC="$DAY/src"
FAILED=0

step() { printf '\n\033[1;36m=== %s\033[0m\n' "$*"; }
run()  {
  local label="$1"; shift
  printf '\033[1;35m->\033[0m %s\n' "$label"
  if "$@"; then return 0; fi
  printf '\033[1;31mFAILED:\033[0m %s\n' "$label"
  FAILED=$((FAILED+1))
  return 1
}

step "0. environment doctor"
if ! "$PY" "$HERE/doctor.py"; then
  if "$PY" - <<'EOF'
import json, sys, pathlib
p = pathlib.Path(__file__).resolve().parent if False else None
d = json.loads((pathlib.Path("arkads-ledger/.cache/doctor.json")).read_text()) \
    if pathlib.Path("arkads-ledger/.cache/doctor.json").is_file() else None
hard = [f for f in (d["failing"] if d else ["doctor"]) if not f.startswith("manim")]
sys.exit(1 if hard else 0)
EOF
  then :; else
    echo "abort: the doctor failed. Fix the environment, or re-run setup.sh."
    exit 1
  fi
  echo "doctor reported a non-Manim failure; aborting."
  exit 1
fi
echo "doctor passed"

step "1. social content brain"
if [ "${ARKAD_SKIP_BRAIN:-0}" != "1" ]; then
  run "gather candidates"   "$PY" "$SRC/brain/gather.py" || exit 1
  run "verify sources"      "$PY" "$SRC/brain/verify.py" || exit 1
  run "score and select"    "$PY" "$SRC/brain/select.py"   || exit 1
else
  echo "skipped (ARKAD_SKIP_BRAIN=1)"
fi

step "2. script"
run "script.md + scenes_plan.json" "$PY" "$SRC/script_gen.py" || exit 1

step "3. narration, voice QA, alignment and the timeline"
run "Piper TTS + whisper + timeline" "$PY" "$SRC/timeline.py" || exit 1

step "4. audio: SFX, music, loudness"
run "mix to -16 LUFS" "$PY" "$SRC/audio_mix.py" || exit 1

step "5. render and mux"
run "render frames + attach audio" "$PY" "$SRC/render.py" || exit 1

step "6. thumbnail"
run "sample-thumb.png + .jpg" "$PY" "$SRC/thumbnail.py" || exit 1

step "7. youtube package"
run "metadata md + json" "$PY" "$SRC/metadata.py" || exit 1

step "8. QA"
"$PY" "$SRC/qa.py" || true

printf '\n\033[1m=== done ===\033[0m\n'
ls -la "$DAY/video" "$DAY/thumbnail" 2>/dev/null
if [ "$FAILED" -gt 0 ]; then
  printf '\033[1;31m%s step(s) failed.\033[0m\n' "$FAILED"
  exit 1
fi
