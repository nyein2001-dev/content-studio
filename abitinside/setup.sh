#!/usr/bin/env bash
# =====================================================================
#  A Bit Inside - environment bootstrap
#  Fully ROOTLESS. No sudo, no apt, no system Python, no API keys.
#  Idempotent: run it as many times as you like.
#
#    bash abitinside/setup.sh
#
#  Installs, all inside the repo or the user home:
#    tools/uv                 -> uv + CPython 3.11 (python-build-standalone)
#    .venv/                   -> PEP 405 virtualenv with every Python package
#    tools/cdeps/             -> conda-forge cairo/pango/pkg-config headers
#    tools/ffmpeg/            -> static FFmpeg >= 6.0 (libx264, aac,
#                                loudnorm, ebur128)
#    assets/fonts/            -> Poppins + JetBrains Mono TTFs
#    assets/voices/           -> Piper en_US-ryan-high
#    .cache/huggingface/      -> faster-whisper base.en
# =====================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "$HERE/env.sh"

say()  { printf '\033[36m[setup]\033[0m %s\n' "$*"; }
step() { printf '\033[1;36m[setup] ==> %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m[setup] FATAL: %s\033[0m\n' "$*" >&2; exit 1; }

mkdir -p "$TOOLS_DIR" "$FONTS_DIR" "$VOICES_DIR" "$ABIT_HOME/.cache" "$USERBIN" "$HOME/.cache"

# ---------------------------------------------------------------- 0. host
step "Detecting host"
case "$(uname -s)" in
  Linux)  HOST_OK=1 ;;
  Darwin) HOST_OK=1 ;;
  MINGW*|MSYS*|CYGWIN*) HOST_OK=1 ;;
  *) HOST_OK=0 ;;
esac
say "kernel: $(uname -sr)   cpus: $(nproc 2>/dev/null || sysctl -n hw.ncpu)   mem: $(free -g 2>/dev/null | awk '/Mem:/{print $2}')GB"
[ "$HOST_OK" = "1" ] || die "Unsupported OS. Run inside WSL2/Ubuntu, macOS, or Git Bash."

# ---------------------------------------------------------------- 1. curl
command -v curl >/dev/null 2>&1 || die "curl is required and was not found (WSL2 Ubuntu ships it)."

# ---------------------------------------------------------------- 2. uv + CPython 3.11
step "uv + CPython 3.11"
if [ ! -x "$USERBIN/uv" ]; then
  say "installing uv from https://astral.sh/uv/install.sh"
  curl -fsSL https://astral.sh/uv/install.sh -o "$ABIT_HOME/.cache/uv-install.sh" \
    || die "could not download the uv installer"
  UV_INSTALL_DIR="$USERBIN" sh "$ABIT_HOME/.cache/uv-install.sh" >/dev/null 2>&1 \
    || die "uv installer failed"
fi
[ -x "$USERBIN/uv" ] || die "uv is still not present at $USERBIN/uv"
"$USERBIN/uv" --version || die "uv is not runnable"
say "uv $("$USERBIN/uv" --version | awk '{print $2}')"

if ! "$USERBIN/uv" python find 3.11 >/dev/null 2>&1; then
  say "downloading standalone CPython 3.11"
  "$USERBIN/uv" python install 3.11 || die "uv could not install CPython 3.11"
fi
say "python 3.11 -> $("$USERBIN/uv" python find 3.11)"

# ---------------------------------------------------------------- 3. venv
step "virtual environment at $VENV_DIR"
if [ ! -x "$PY" ]; then
  rm -rf "$VENV_DIR"
  "$USERBIN/uv" venv --python 3.11 "$VENV_DIR" || die "uv venv failed"
fi
"$PY" -c 'import sys; assert sys.version_info[:2]==(3,11), sys.version' \
  || die "venv is not CPython 3.11"
say "venv python: $("$PY" -c 'import platform;print(platform.python_version())')"

# ------------------------------------------------- 4. cairo dev headers (rootless)
step "cairo / pango headers via rootless micromamba (conda-forge)"
if [ ! -f "$CDEPS_DIR/include/cairo/cairo.h" ]; then
  if [ ! -x "$MMAMBA_DIR/bin/micromamba" ]; then
    say "downloading micromamba"
    curl -fsSL "https://micro.mamba.pm/api/micromamba/linux-64/latest" \
      -o "$ABIT_HOME/.cache/micromamba.tar.bz2" || die "micromamba download failed"
    rm -rf "$MMAMBA_DIR"; mkdir -p "$MMAMBA_DIR"
    # This minimal WSL image has no bzip2 binary; CPython's tarfile handles .bz2.
    "$PY" - "$ABIT_HOME/.cache/micromamba.tar.bz2" "$MMAMBA_DIR" <<'PY'
import sys, tarfile
with tarfile.open(sys.argv[1], "r:bz2") as t:
    t.extractall(sys.argv[2], filter="data")
PY
  fi
  say "solving conda-forge environment (cairo, pango, pkg-config) - first run can take a few minutes"
  rm -rf "$CDEPS_DIR"
  "$MMAMBA_DIR/bin/micromamba" create -y -q -r "$ABIT_HOME/.cache/mamba" -p "$CDEPS_DIR" \
      -c conda-forge cairo pango pkg-config \
      || die "micromamba could not create the cairo prefix"
fi
# cairo.pc chains through zlib/libpng/freetype/fontconfig/pixman, and pycairo's
# surface.c includes cairo-xlib.h, so the real X11 protocol headers are needed too.
# The X11 stack moved to the `xorg-*` package names on conda-forge; --override-channels
# is required because the legacy `xorg` channel 404s on noarch.
"$MMAMBA_DIR/bin/micromamba" install -y -q --override-channels --platform linux-64 \
    -r "$ABIT_HOME/.cache/mamba" -p "$CDEPS_DIR" -c conda-forge \
    zlib libpng freetype fontconfig pixman expat brotli bzip2 \
    xorg-xorgproto xorg-libx11 xorg-libxext xorg-libxrender xorg-kbproto \
    xorg-libxau xorg-libxdmcp \
    || die "micromamba could not install the cairo/X11 dependencies"
[ -f "$CDEPS_DIR/include/X11/X.h" ] || die "X11 protocol headers missing from $CDEPS_DIR"
say "X11 protocol headers OK"
"$PY" - "$CDEPS_DIR" <<'PY' || die "could not synthesise missing pkg-config entries"
import os, re, sys
prefix = sys.argv[1]
pcdir = os.path.join(prefix, "lib", "pkgconfig")
stub = """prefix={p}
Name: {n}
Description: stub pkg-config entry (generated by abitinside/setup.sh)
Version: 7.0.0
Cflags: -I${{prefix}}/include
"""
for _ in range(6):
    mods = set()
    for f in os.listdir(pcdir):
        if not f.endswith(".pc"):
            continue
        for line in open(os.path.join(pcdir, f), encoding="utf-8", errors="replace"):
            m = re.match(r"\s*Requires(?:\.private)?:\s*(.*)", line)
            if m:
                mods.update(re.split(r"[,\s]+", m.group(1).strip()))
    mods = {m for m in mods if m and not os.path.exists(os.path.join(pcdir, m + ".pc"))}
    if not mods:
        print("   pkg-config dependency graph complete")
        break
    for m in sorted(mods):
        open(os.path.join(pcdir, m + ".pc"), "w").write(stub.format(p=prefix, n=m))
        print("   synthesised", m + ".pc")
else:
    print("   WARNING: pkg-config stubs did not converge", file=sys.stderr)
PY
[ -f "$CDEPS_DIR/lib/pkgconfig/zlib.pc" ] || die "zlib.pc missing from $CDEPS_DIR"
[ -f "$CDEPS_DIR/lib/pkgconfig/expat.pc" ] || die "expat.pc missing from $CDEPS_DIR"
[ -f "$CDEPS_DIR/include/cairo/cairo.h" ] || die "cairo.h missing from $CDEPS_DIR"
say "cairo headers OK ($(pkg-config --modversion cairo 2>/dev/null || echo 'pkg-config not yet on PATH'))"

# ------------------------------------------- 4b. C toolchain (rootless, conda-forge)
step "C toolchain via rootless micromamba (needed: pycairo has no wheel and must be compiled)"
if ! command -v cc >/dev/null 2>&1 && [ ! -x "$TC_DIR/bin/x86_64-conda-linux-gnu-gcc" ]; then
  if [ ! -x "$MMAMBA_DIR/bin/micromamba" ]; then
    curl -fsSL "https://micro.mamba.pm/api/micromamba/linux-64/latest" \
      -o "$ABIT_HOME/.cache/micromamba.tar.bz2" || die "micromamba download failed"
    rm -rf "$MMAMBA_DIR"; mkdir -p "$MMAMBA_DIR"
    "$PY" - "$ABIT_HOME/.cache/micromamba.tar.bz2" "$MMAMBA_DIR" <<'PY'
import sys, tarfile
with tarfile.open(sys.argv[1], "r:bz2") as t:
    t.extractall(sys.argv[2], filter="data")
PY
  fi
  say "installing gcc/binutils (a minimal WSL image ships no compiler and sudo is unavailable)"
  "$MMAMBA_DIR/bin/micromamba" create -y -q -r "$ABIT_HOME/.cache/mamba" -p "$TC_DIR" \
      -c conda-forge gcc gxx binutils make \
      || die "micromamba could not create the toolchain prefix"
fi
export PATH="$TC_DIR/bin:$PATH"
command -v gcc >/dev/null 2>&1 || die "no C compiler available after installing the toolchain"
say "compiler: $(gcc --version | head -1)"

# ---------------------------------------------------------------- 5. Python packages
step "Python packages"
uvpip() { "$USERBIN/uv" pip install --python "$PY" "$@"; }
REQ=(numpy scipy matplotlib pillow soundfile pyloudnorm fonttools
     piper-tts faster-whisper pyspellchecker requests feedparser tqdm edge-tts)
"$PY" - <<'PY' || uvpip "${REQ[@]}"
import importlib.util as u, sys
need = ["numpy","scipy","matplotlib","PIL","soundfile","pyloudnorm","fontTools",
        "piper","faster_whisper","spellchecker","requests","feedparser","tqdm","edge_tts"]
missing = [m for m in need if u.find_spec(m) is None]
sys.exit(0 if not missing else 1)
PY
uvpip "${REQ[@]}" || die "pip install of core packages failed"

# pycairo has no wheels on PyPI: compile it against the conda-forge cairo.
if ! "$PY" -c 'import cairo; assert cairo.version' 2>/dev/null; then
  step "building pycairo from source (no PyPI wheel is published)"
  uvpip --no-binary pycairo pycairo || die "pycairo build failed"
fi
"$PY" -c 'import cairo; print("   pycairo", cairo.version, "cairo", cairo.cairo_version_string())' \
  || die "pycairo cannot import"

# manim is optional and must never block the build.
if [ "${ABIT_SKIP_MANIM:-0}" != "1" ]; then
  step "manim (best effort, non-blocking)"
  if "$PY" -c 'import manim' 2>/dev/null; then
    say "manim already importable"
  else
    uvpip manim >/dev/null 2>&1 \
      && say "manim installed" \
      || say "manim unavailable (needs more system libs) - continuing, pycairo is the renderer"
  fi
fi

# ---------------------------------------------------------------- 6. FFmpeg
step "FFmpeg >= 6.0 (static, libx264 + aac + loudnorm + ebur128)"
if [ ! -x "$FFMPEG" ]; then
  say "downloading johnvansickle static build"
  curl -fsSL "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz" \
    -o "$ABIT_HOME/.cache/ffmpeg-static.tar.xz" || die "FFmpeg download failed"
  rm -rf "$FFMPEG_DIR"; mkdir -p "$FFMPEG_DIR/bin"
  # xz/bzip2 binaries may be absent on a minimal image; CPython's tarfile handles both.
  "$PY" - "$ABIT_HOME/.cache/ffmpeg-static.tar.xz" "$ABIT_HOME/.cache" <<'PY'
import sys, tarfile
with tarfile.open(sys.argv[1], "r:xz") as t:
    t.extractall(sys.argv[2], filter="data")
PY
  _d=$(find "$ABIT_HOME/.cache" -maxdepth 1 -type d -name 'ffmpeg-*-amd64-static' | head -1)
  [ -n "$_d" ] || die "static FFmpeg folder not found after extract"
  cp "$_d/ffmpeg" "$_d/ffprobe" "$FFMPEG_DIR/bin/"
  chmod +x "$FFMPEG_DIR/bin/ffmpeg" "$FFMPEG_DIR/bin/ffprobe"
fi
[ -x "$FFMPEG" ] || die "FFmpeg missing at $FFMPEG"
say "ffmpeg $("$FFMPEG" -version | head -1 | awk '{print $3}')"

# ---------------------------------------------------------------- 7. fonts
step "fonts (loaded by file path, never by system lookup)"
fetch() { curl -fsSL "$1" -o "$2" && [ -s "$2" ]; }
FONT_BASE="https://raw.githubusercontent.com/google/fonts/main/ofl"
declare -A FONTS=(
  ["Poppins-Bold.ttf"]="$FONT_BASE/poppins/Poppins-Bold.ttf"
  ["Poppins-SemiBold.ttf"]="$FONT_BASE/poppins/Poppins-SemiBold.ttf"
  ["Poppins-Regular.ttf"]="$FONT_BASE/poppins/Poppins-Regular.ttf"
  ["JetBrainsMono.ttf"]="$FONT_BASE/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf"
)
for name in "${!FONTS[@]}"; do
  if [ ! -s "$FONTS_DIR/$name" ]; then
    fetch "${FONTS[$name]}" "$FONTS_DIR/$name" || say "WARN could not fetch $name"
  fi
done
for name in "${!FONTS[@]}"; do
  [ -s "$FONTS_DIR/$name" ] && say "  $name" || say "  MISSING $name"
done

# ---------------------------------------------------------------- 8. Piper voice
step "Piper neural voice (offline)"
VOICE_ROOT="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US"
# Fallback chain: try each in order, stop at the first that lands. On a later run
# the preferred voice already exists, so the chain does not re-download anything.
VOICES_OK=0
for spec in "ryan/high/en_US-ryan-high" "lessac/high/en_US-lessac-high" "lessac/medium/en_US-lessac-medium"; do
  sub="${spec%/*}"; name="${spec##*/}"
  if [ -s "$VOICES_DIR/$name.onnx" ] && [ -s "$VOICES_DIR/$name.onnx.json" ]; then
    say "  already have $name"
    VOICES_OK=1
    continue
  fi
  if [ "$VOICES_OK" = "1" ]; then continue; fi
  say "trying voice $name"
  if fetch "$VOICE_ROOT/$sub/$name.onnx" "$VOICES_DIR/$name.onnx" \
     && fetch "$VOICE_ROOT/$sub/$name.onnx.json" "$VOICES_DIR/$name.onnx.json"; then
    say "  got $name"
    VOICES_OK=1
  else
    rm -f "$VOICES_DIR/$name.onnx" "$VOICES_DIR/$name.onnx.json"
  fi
done
[ "$VOICES_OK" = "1" ] || say "WARN no Piper voice available yet (retry on next run)"
ls "$VOICES_DIR"/*.onnx >/dev/null 2>&1 \
  || say "WARN no Piper voice downloaded yet (will retry on next run)"
ls -la "$VOICES_DIR" 2>/dev/null | grep -E '\.onnx$' || true

# ---------------------------------------------------------------- 9. whisper model
step "faster-whisper base.en (offline word timestamps)"
"$PY" - <<'PY' || say "WARN whisper model download failed; retry on next run"
import os
from faster_whisper import WhisperModel
WhisperModel("base.en", device="cpu", compute_type="int8", download_root=os.environ["HF_HOME"])
print("   base.en ready")
PY

# ---------------------------------------------------------------- 10. done
step "bootstrap complete"
say "venv      : $VENV_DIR"
say "ffmpeg    : $FFMPEG"
say "next      : $PY $ABIT_HOME/doctor.py"