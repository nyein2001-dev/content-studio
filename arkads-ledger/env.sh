#!/usr/bin/env bash
# Arkad's Ledger - shared environment (rootless, no sudo required).
# Source this file:  source arkads-ledger/env.sh
# It only exports variables and appends to PATH; it installs nothing.

_LEDGER_ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export LEDGER_HOME="$_LEDGER_ENV_DIR"
unset _LEDGER_ENV_DIR

export LEDGER_REPO="$(cd "$LEDGER_HOME/.." && pwd)"
export LEDGER_DAY_DIR="${LEDGER_DAY_DIR:-$LEDGER_HOME/2026-10-13}"

# One virtual environment for the whole studio, shared with the other channel.
if [ -x "$LEDGER_REPO/.venv/bin/python" ]; then
  export VENV_DIR="$LEDGER_REPO/.venv"
else
  export VENV_DIR="$LEDGER_HOME/.venv"
fi

# Reuse the studio's ffmpeg, cairo/pango prefix and rootless toolchain when present
# so a bootstrap here is fast; setup.sh fetches its own copy otherwise.
if [ -x "$LEDGER_REPO/abitinside/tools/ffmpeg/bin/ffmpeg" ]; then
  export TOOLS_DIR="${TOOLS_DIR:-$LEDGER_REPO/abitinside/tools}"
else
  export TOOLS_DIR="${TOOLS_DIR:-$LEDGER_HOME/tools}"
fi
export CDEPS_DIR="$TOOLS_DIR/cdeps"
export MMAMBA_DIR="$TOOLS_DIR/micromamba"
export USERBIN="$HOME/.local/bin"

export ASSETS_DIR="$LEDGER_HOME/assets"
export FONTS_DIR="$ASSETS_DIR/fonts"
export VOICES_DIR="$ASSETS_DIR/voices"
export GEO_DIR="$ASSETS_DIR/geo"

# Keep every heavy cache off the slow Windows mount (/mnt/c is DrvFs).
export UV_CACHE_DIR="${UV_CACHE_DIR:-$HOME/.cache/uv}"
export HF_HOME="${HF_HOME:-$LEDGER_HOME/.cache/huggingface}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-$HOME/.cache/matplotlib}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"

# This box has 2 cores and ~3.9 GB RAM. Never oversubscribe.
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-2}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-2}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-2}"
export CUDA_VISIBLE_DEVICES=""
export TOKENIZERS_PARALLELISM="false"
export PYTHONHASHSEED="0"
export PYTHONDONTWRITEBYTECODE="1"

# WSL resolves IPv6 but has no IPv6 route, so a client that prefers IPv6 hangs.
# These keep every downloader on IPv4 without needing root.
export UV_HTTP_TIMEOUT="${UV_HTTP_TIMEOUT:-120}"

export PKG_CONFIG_PATH="$CDEPS_DIR/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
export LD_LIBRARY_PATH="$CDEPS_DIR/lib:${LD_LIBRARY_PATH:-}"
export GI_TYPELIB_PATH="$CDEPS_DIR/lib/girepository-1.0:${GI_TYPELIB_PATH:-}"

export PATH="$TOOLS_DIR/ffmpeg/bin:$USERBIN:$MMAMBA_DIR/bin:$VENV_DIR/bin:$CDEPS_DIR/bin:$PATH"
export PYTHONPATH="$LEDGER_REPO:$LEDGER_HOME/2026-10-13/src:$LEDGER_HOME/src:${PYTHONPATH:-}"

export PY="$VENV_DIR/bin/python"
export FFMPEG="$TOOLS_DIR/ffmpeg/bin/ffmpeg"
export FFPROBE="$TOOLS_DIR/ffmpeg/bin/ffprobe"