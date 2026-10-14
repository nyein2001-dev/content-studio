#!/usr/bin/env bash
# A Bit Inside - shared environment (rootless, no sudo required).
# Source this file:  source abitinside/env.sh
# It only exports variables and appends to PATH; it installs nothing.

# Resolve the repository root from this file's location (works under any shell).
_ABIT_ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export ABIT_HOME="$_ABIT_ENV_DIR"
unset _ABIT_ENV_DIR

export ABIT_REPO="$(cd "$ABIT_HOME/.." && pwd)"
export ABIT_DAY_DIR="${ABIT_DAY_DIR:-$ABIT_HOME/2026-10-13}"

export VENV_DIR="$ABIT_HOME/.venv"
export TOOLS_DIR="$ABIT_HOME/tools"
export CDEPS_DIR="$TOOLS_DIR/cdeps"
export TC_DIR="$TOOLS_DIR/toolchain"
export FFMPEG_DIR="$TOOLS_DIR/ffmpeg"
export MMAMBA_DIR="$TOOLS_DIR/micromamba"
export USERBIN="$HOME/.local/bin"

export ASSETS_DIR="$ABIT_HOME/assets"
export FONTS_DIR="$ASSETS_DIR/fonts"
export VOICES_DIR="$ASSETS_DIR/voices"

# Keep every heavy cache off the slow Windows mount (/mnt/c is DrvFs).
export UV_CACHE_DIR="${UV_CACHE_DIR:-$HOME/.cache/uv}"
export HF_HOME="${HF_HOME:-$ABIT_HOME/.cache/huggingface}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-$HOME/.cache/matplotlib}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"

# Deterministic, CPU-only, memory-frugal (this box has ~3.9 GB RAM).
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-2}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-2}"
export CUDA_VISIBLE_DEVICES=""
export TOKENIZERS_PARALLELISM="false"
export PYTHONHASHSEED="0"
export PYTHONDONTWRITEBYTECODE="1"

# cairo / pango / freetype from the rootless conda-forge prefix, so the
# pycairo wheel we compile from source can find headers (build) and the
# shared library (runtime).
export PKG_CONFIG_PATH="$CDEPS_DIR/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
export LD_LIBRARY_PATH="$CDEPS_DIR/lib:${LD_LIBRARY_PATH:-}"
export GI_TYPELIB_PATH="$CDEPS_DIR/lib/girepository-1.0:${GI_TYPELIB_PATH:-}"
# Rootless C toolchain (conda-forge gcc); only needed to compile pycairo once.
export CC="${CC:-x86_64-conda-linux-gnu-gcc}"
export CXX="${CXX:-x86_64-conda-linux-gnu-g++}"
export AR="${AR:-x86_64-conda-linux-gnu-ar}"

export PATH="$FFMPEG_DIR/bin:$USERBIN:$MMAMBA_DIR/bin:$VENV_DIR/bin:$TC_DIR/bin:$CDEPS_DIR/bin:$PATH"

export PY="$VENV_DIR/bin/python"
export FFMPEG="$FFMPEG_DIR/bin/ffmpeg"
export FFPROBE="$FFMPEG_DIR/bin/ffprobe"