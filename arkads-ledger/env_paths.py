"""Resolve the Arkad's Ledger paths without needing a shell.

doctor.py runs under a bare `python`, so it cannot rely on env.sh being sourced.
These are the same values env.sh exports.
"""
from __future__ import annotations

import os
from pathlib import Path

HOME = Path(__file__).resolve().parent
REPO = HOME.parent
VENV = REPO / ".venv" if (REPO / ".venv" / "bin" / "python").is_file() else HOME / ".venv"
PY = VENV / "bin" / "python"
ASSETS = HOME / "assets"
FONTS = ASSETS / "fonts"
VOICES = ASSETS / "voices"
GEO = ASSETS / "geo"
DAY = Path(os.environ.get("LEDGER_DAY_DIR", HOME / "2026-10-13"))

TOOLS = REPO / "abitinside" / "tools" if (REPO / "abitinside" / "tools" / "ffmpeg").is_dir() \
    else HOME / "tools"
FFMPEG = os.environ.get("FFMPEG") or str(TOOLS / "ffmpeg" / "bin" / "ffmpeg")
FFPROBE = os.environ.get("FFPROBE") or str(TOOLS / "ffmpeg" / "bin" / "ffprobe")
CDEPS = TOOLS / "cdeps"

HF_HOME = os.environ.get("HF_HOME") or str(HOME / ".cache" / "huggingface")
CACHE = HOME / ".cache"

# cairo/pango come from the studio's rootless prefix; make it visible before pycairo loads
if CDEPS.is_dir():
    _ld = str(CDEPS / "lib")
    if _ld not in os.environ.get("LD_LIBRARY_PATH", ""):
        os.environ["LD_LIBRARY_PATH"] = _ld + os.pathsep + os.environ.get("LD_LIBRARY_PATH", "")
    _pc = str(CDEPS / "lib" / "pkgconfig")
    if _pc not in os.environ.get("PKG_CONFIG_PATH", ""):
        os.environ["PKG_CONFIG_PATH"] = _pc + os.pathsep + os.environ.get("PKG_CONFIG_PATH", "")

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "2")
os.environ.setdefault("MPLCONFIGDIR", str(CACHE / "matplotlib"))

if str(REPO) not in os.environ.get("PYTHONPATH", ""):
    os.environ["PYTHONPATH"] = str(REPO) + os.pathsep + os.environ.get("PYTHONPATH", "")