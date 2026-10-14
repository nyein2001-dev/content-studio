"""Production narration is pipeline.tts. This file must not choose a voice."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline.tts import main  # noqa: E402

if __name__ == "__main__":
    sys.argv = [sys.argv[0], str(Path(__file__).resolve().parents[1])]
    sys.exit(main())
