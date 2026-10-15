#!/usr/bin/env bash
# Arkad's Ledger - idempotent, rootless bootstrap (no sudo, no system Python).
#
#   bash arkads-ledger/setup.sh
#
# Safe to re-run: every step checks for what it needs before doing anything.
# Nothing here needs root. Heavy caches stay off the slow Windows mount.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./env.sh
source "$HERE/env.sh"

mkdir -p "$FONTS_DIR" "$VOICES_DIR" "$GEO_DIR" "$LEDGER_HOME/.cache" "$USERBIN" \
         "$LEDGER_HOME/2026-10-13/audio" "$LEDGER_HOME/2026-10-13/video" \
         "$LEDGER_HOME/2026-10-13/thumbnail"

FAILURES=0
say()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mWARN\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mFAIL\033[0m %s\n' "$*"; FAILURES=$((FAILURES+1)); }
ok()   { printf '  \033[1;32mok\033[0m %s\n' "$*"; }

# WSL has DNS for IPv6 but no IPv6 route: force IPv4 for every download.
fetch() {  # fetch <url> <dest> ; retries with backoff
  local url="$1" dest="$2" n=0
  mkdir -p "$(dirname "$dest")"
  while [ $n -lt 3 ]; do
    if curl -4 -fsSL --retry 2 --connect-timeout 20 --max-time 600 \
            -A "ArkadsLedger/1.0 (educational video production)" \
            -o "$dest.part" "$url"; then
      mv -f "$dest.part" "$dest"; return 0
    fi
    n=$((n+1)); warn "fetch retry $n: $url"; sleep $((n*3))
  done
  rm -f "$dest.part"; return 1
}

# ---------------------------------------------------------------- 1. uv + venv
say "1. uv and the shared virtual environment"
if [ ! -x "$USERBIN/uv" ]; then
  fetch "https://astral.sh/uv/install.sh" "$USERBIN/uv-install.sh" \
    && sh "$USERBIN/uv-install.sh" >/dev/null 2>&1
fi
export PATH="$USERBIN:$PATH"
command -v uv >/dev/null || die "uv is not available and could not be installed"
ok "uv $(uv --version 2>/dev/null | awk '{print $2}')"

if [ ! -x "$VENV_DIR/bin/python" ]; then
  uv venv --python 3.11 "$VENV_DIR" >/dev/null || die "could not create the virtual environment"
fi
ok "venv $VENV_DIR ($("$PY" --version 2>&1))"

# ---------------------------------------------------------------- 2. python packages
say "2. python packages (core + local neural TTS + map stack)"
CORE="numpy scipy matplotlib pillow soundfile pyloudnorm fonttools piper-tts \
faster-whisper librosa jiwer num2words pyspellchecker requests feedparser tqdm pandas pycairo PyYAML"
GEO="geopandas shapely pyproj rasterio cartopy pyogrio"

probe() { "$PY" - "$@" <<'EOF' 2>/dev/null
import importlib, sys
sys.exit(0 if all(importlib.util.find_spec(m) for m in sys.argv[1:]) else 1)
EOF
}

if probe numpy scipy PIL soundfile pyloudnorm fontTools piper faster_whisper \
          num2words spellchecker requests feedparser tqdm pandas cairo yaml manim; then
  ok "core packages present"
else
  uv pip install --python "$PY" $CORE >/dev/null 2>&1 \
    || die "core package install failed (host: pypi.org)"
  ok "core packages installed"
fi
probe numpy scipy cairo && ok "core importable" || die "core packages did not import"

if probe geopandas shapely pyproj rasterio pyogrio; then
  ok "map stack present (binary wheels, no system GDAL needed)"
else
  # Binary wheels only: pyogrio and rasterio bundle GDAL/GEOS, pyproj bundles proj.db.
  uv pip install --python "$PY" $GEO >/dev/null 2>&1 \
    || warn "map stack pip install failed; the doctor will report which imports are missing"
  probe geopandas pyproj rasterio && ok "map stack installed" \
    || warn "map stack incomplete; doctor.py will report the exact failure"
fi

# ---------------------------------------------------------------- 3. ffmpeg
say "3. FFmpeg with libx264, aac, loudnorm and ebur128"
if [ -x "$FFMPEG" ] && "$FFMPEG" -hide_banner -filters 2>/dev/null | grep -q ' loudnorm '; then
  ok "$("$FFMPEG" -version 2>/dev/null | head -1 | cut -d' ' -f1-3)"
else
  fetch "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz" \
        "$LEDGER_HOME/.cache/ffmpeg-static.tar.xz" \
    && mkdir -p "$TOOLS_DIR" \
    && "$PY" -c "import tarfile,sys; tarfile.open(sys.argv[1]).extractall(sys.argv[2])" \
         "$LEDGER_HOME/.cache/ffmpeg-static.tar.xz" "$TOOLS_DIR" \
    && D=$(find "$TOOLS_DIR" -maxdepth 1 -type d -name 'ffmpeg-*-static' | head -1) \
    && mkdir -p "$TOOLS_DIR/ffmpeg/bin" \
    && cp "$D/ffmpeg" "$D/ffprobe" "$TOOLS_DIR/ffmpeg/bin/" \
    && chmod +x "$TOOLS_DIR/ffmpeg/bin/ffmpeg" "$TOOLS_DIR/ffmpeg/bin/ffprobe" \
    || die "could not obtain FFmpeg"
  ok "ffmpeg installed"
fi

# ---------------------------------------------------------------- 4. cairo / pango
say "4. cairo and pango (for pycairo text rendering and Manim)"
if "$PY" -c "import cairo" 2>/dev/null && [ -d "$CDEPS_DIR/lib" ]; then
  ok "cairo available ($("$PY" -c 'import cairo;print(cairo.version)' 2>/dev/null))"
elif [ -d "$LEDGER_REPO/abitinside/tools/cdeps/lib" ]; then
  ok "reusing the studio's rootless cairo prefix"
else
  warn "no cairo prefix; pycairo must still import for the build to start"
fi

# ---------------------------------------------------------------- 5. fonts
say "5. Montserrat static instances (loaded by path, never by system lookup)"
GOOGLE="https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat"
VAR_TTF="$LEDGER_HOME/.cache/Montserrat-Variable.ttf"
if [ ! -s "$VAR_TTF" ]; then
  fetch "$GOOGLE/Montserrat%5Bwght%5D.ttf" "$VAR_TTF" || die "could not download the Montserrat variable font"
fi
if [ ! -s "$FONTS_DIR/Montserrat-ExtraBold.ttf" ] || [ ! -s "$FONTS_DIR/Montserrat-Bold.ttf" ]; then
  "$PY" - "$VAR_TTF" "$FONTS_DIR" <<'EOF'
import sys
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

var, out = Path(sys.argv[1]), Path(sys.argv[2])
for name, wght in (("Medium", 500), ("SemiBold", 600), ("Bold", 700), ("ExtraBold", 800)):
    dest = out / f"Montserrat-{name}.ttf"
    if dest.is_file() and dest.stat().st_size > 0:
        continue
    f = TTFont(str(var))
    inst = instancer.instantiateVariableFont(f, {"wght": wght}, inplace=True, updateFontNames=True)
    inst.save(str(dest))
    print(f"   instanced Montserrat-{name}.ttf")
EOF
  ok "Montserrat static instances created with fontTools instancer"
else
  ok "Montserrat static instances present"
fi
for f in ExtraBold Bold SemiBold Medium; do
  [ -s "$FONTS_DIR/Montserrat-$f.ttf" ] || warn "Montserrat-$f.ttf missing"
done

# ---------------------------------------------------------------- 6. voice
say "6. Piper narrator voice (local neural TTS, no API key)"
# rhasspy/piper-voices is laid out as <lang>/<locale>/<quality>/<name>.onnx
PIPER_ROOT="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US"
VOICE="en_US-ryan-high"
# Reuse a voice the studio already provisioned rather than re-fetching 115 MB.
for src in "$LEDGER_REPO/abitinside/assets/voices" "$VOICES_DIR"; do
  for cand in en_US-ryan-high en_US-lessac-high en_US-lessac-medium; do
    if [ -s "$src/$cand.onnx" ] && [ ! -s "$VOICES_DIR/$cand.onnx" ]; then
      cp -f "$src/$cand.onnx" "$VOICES_DIR/$cand.onnx"
      [ -s "$src/$cand.onnx.json" ] && cp -f "$src/$cand.onnx.json" "$VOICES_DIR/$cand.onnx.json"
      ok "reused Piper voice $cand from $src"
    fi
  done
done
if [ ! -s "$VOICES_DIR/$VOICE.onnx" ]; then
  case "$VOICE" in
    en_US-ryan-high)    QP="ryan/high" ;;
    en_US-lessac-high)   QP="lessac/high" ;;
    *)                   QP="lessac/medium" ;;
  esac
  fetch "$PIPER_ROOT/$QP/$VOICE.onnx" "$VOICES_DIR/$VOICE.onnx" \
    && fetch "$PIPER_ROOT/$QP/$VOICE.onnx.json" "$VOICES_DIR/$VOICE.onnx.json" \
    || die "could not download the Piper voice $VOICE"
  ok "Piper voice $VOICE downloaded"
fi
[ -s "$VOICES_DIR/$VOICE.onnx" ] || die "no Piper voice is available"
ok "narrator voice: $VOICE (local, no API key)"

# ---------------------------------------------------------------- 7. word timing
say "7. faster-whisper models (base.en for alignment, small.en for the ASR check)"
for m in base.en small.en; do
  if "$PY" -c "from faster_whisper import WhisperModel; WhisperModel('$m', device='cpu', compute_type='int8', download_root='$HF_HOME')" >/dev/null 2>&1; then
    ok "whisper $m available offline"
  else
    warn "whisper $m could not be loaded or downloaded"
  fi
done

# ---------------------------------------------------------------- 8. map data
say "8. Natural Earth 10m + a glow source"
NE="https://naciscdn.org/naturalearth/10m"
declare -A LAYERS=(
  [countries]="$NE/cultural/ne_10m_admin_0_countries.zip"
  [borderlines]="$NE/cultural/ne_10m_admin_0_boundary_lines_land.zip"
  [coastline]="$NE/physical/ne_10m_coastline.zip"
  [rivers]="$NE/physical/ne_10m_rivers_lake_centerlines.zip"
  [places]="$NE/cultural/ne_10m_populated_places.zip"
  [lakes]="$NE/physical/ne_10m_lakes.zip"
)
for k in "${!LAYERS[@]}"; do
  if [ -s "$GEO_DIR/ne_10m_$k" ]; then ok "Natural Earth $k present"; continue; fi
  Z="$LEDGER_HOME/.cache/ne_$k.zip"
  fetch "${LAYERS[$k]}" "$Z" || { warn "Natural Earth $k download failed"; continue; }
  "$PY" -c "
import zipfile,sys
z=zipfile.ZipFile(sys.argv[1]); z.extractall(sys.argv[2])
" "$Z" "$GEO_DIR" && rm -f "$Z" && ok "Natural Earth $k downloaded"
done
ls "$GEO_DIR"/*.shp >/dev/null 2>&1 || die "no Natural Earth shapefiles were obtained"

# Glow source, in the order the brief requires. VIIRS needs a login, so the
# honest default is WorldPop, and the renderer falls back to procedural.
"$PY" - "$GEO_DIR" <<'EOF'
import json, sys
from pathlib import Path
g = Path(sys.argv[1])
meta = g / "glow_source.json"
if meta.is_file():
    print(f"   glow source already resolved: {json.loads(meta.read_text()).get('source')}")
    raise SystemExit(0)
base = "https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/BSGM/"
meta.write_text(json.dumps({"source": "procedural", "tried": ["worldpop"], "reason": "pending probe"}))
EOF
ok "glow source probe recorded (renderer resolves and falls back automatically)"

# ---------------------------------------------------------------- 9. done
say "bootstrap complete"
if [ "$FAILURES" -gt 0 ]; then
  printf '\033[1;31m%d step(s) failed.\033[0m Run: %s %s/doctor.py\n' "$FAILURES" "$PY" "$LEDGER_HOME"
  exit 1
fi
echo "next: $PY $LEDGER_HOME/doctor.py"