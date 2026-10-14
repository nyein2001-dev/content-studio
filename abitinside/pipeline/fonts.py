"""Regenerate fontconfig from this install's directory, never a hardcoded root."""
from __future__ import annotations

from pathlib import Path

from pipeline.config import ROOT


def write_fonts_conf() -> Path:
    fonts = ROOT / "assets" / "fonts"
    cache = ROOT / ".cache" / "fontconfig"
    cache.mkdir(parents=True, exist_ok=True)
    tpl = (ROOT / "assets" / "fonts.conf.tpl").read_text(encoding="utf-8")
    subs = {
        "FONTS_DIR": str(fonts),
        "CACHE_DIR": str(cache),
        "FONT_POPPINSBOLD": str(fonts / "Poppins-Bold.ttf"),
        "FONT_POPPINSSEMIBOLD": str(fonts / "Poppins-SemiBold.ttf"),
        "FONT_POPPINSNORMAL": str(fonts / "Poppins-Regular.ttf"),
        "FONT_JBMONO": str(fonts / "JetBrainsMono.ttf"),
    }
    text = tpl
    for key, value in subs.items():
        text = text.replace(key, value)
    stale = "Animation" + "ContentStudio"
    if stale in text:
        raise SystemExit("fonts.conf still names the deleted studio tree")
    out = ROOT / "assets" / "fonts.conf"
    out.write_text(text, encoding="utf-8")
    return out
