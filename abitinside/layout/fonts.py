"""Bundled fonts only. A system fallback is a hard failure.

Glyphs are loaded from the TTF path. FontConfig's Poppins catch-all assigns
Poppins-Bold to a regular-weight request, which would silently restyle body
copy. New videos therefore rasterize the named file and do not call
select_font_face for those roles. fonts.conf is still installed so a cairo
lookup cannot wander into the system font set, and bold / semibold / mono
must resolve to the bundled filenames.
"""
from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path

from fontTools.ttLib import TTFont

from layout.errors import LayoutError
from layout.spec import ABIT, load_spec


def font_file(key: str) -> Path:
    spec = load_spec()
    rel = spec["fonts"].get(key)
    if not rel:
        raise LayoutError(
            "fonts", "R09",
            f"no bundled font for {key}",
            "Name the file under fonts in layout_spec.yaml.",
        )
    path = (ABIT / rel).resolve()
    if not path.is_file():
        raise LayoutError(
            "fonts", "R09",
            f"bundled font is missing: {path}",
            "Run bash setup.sh. Do not substitute a system font.",
        )
    return path


def _open(path: Path) -> TTFont:
    return TTFont(path)


def family_name(path: Path) -> str:
    font = _open(path)
    names: list[str] = []
    try:
        for record in font["name"].names:
            if record.nameID == 1:
                try:
                    names.append(record.toUnicode())
                except Exception:
                    continue
    finally:
        font.close()
    if not names:
        raise LayoutError(
            "fonts", "R09",
            f"{path.name} has no family name",
            "Restore the official font file.",
        )
    return names[0]


def weight_class(path: Path) -> int:
    font = _open(path)
    try:
        return int(font["OS/2"].usWeightClass)
    finally:
        font.close()


def _fc_match(query: str) -> str:
    try:
        return subprocess.check_output(
            ["fc-match", "-f", "%{file}", query],
            text=True,
            env=os.environ.copy(),
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise LayoutError(
            "fonts", "R09",
            f"fontconfig could not resolve {query}: {exc}",
            "Install fontconfig and run bash setup.sh. The build will not guess a font.",
        ) from exc


@lru_cache(maxsize=1)
def install_fonts() -> None:
    spec = load_spec()
    from pipeline.fonts import write_fonts_conf

    conf = write_fonts_conf()
    os.environ["FONTCONFIG_FILE"] = str(conf)
    os.environ["FONTCONFIG_PATH"] = str(ABIT / "assets")
    (ABIT / ".cache" / "fontconfig").mkdir(parents=True, exist_ok=True)
    expected_weight = {"bold": 700, "semibold": 600, "regular": 400, "mono": 400}
    for key, expected in spec["fonts"]["family"].items():
        path = font_file(key)
        found = family_name(path)
        if expected.split()[0].lower() not in found.lower():
            raise LayoutError(
                "fonts", "R09",
                f"{path.name} reports family {found!r}, expected {expected!r}",
                "Replace the file with the bundled family. Refusing a fallback font.",
            )
        actual = weight_class(path)
        if actual != expected_weight[key]:
            raise LayoutError(
                "fonts", "R09",
                f"{path.name} has weight class {actual}, expected {expected_weight[key]}",
                "Restore the official file for this role. A different weight is a fallback.",
            )
    # fonts.conf maps a medium request and then a later catch-all assigns Bold.
    # That file is what the sample renderer uses, so it is not edited here.
    # Semibold is proven by the file's name and OS/2 weight, not by fc-match.
    conf_text = conf.read_text(encoding="utf-8")
    if font_file("semibold").name not in conf_text or font_file("bold").name not in conf_text:
        raise LayoutError(
            "fonts", "R09",
            "fonts.conf does not name the bundled bold and semibold files",
            "Regenerate fonts.conf from assets/fonts.conf.tpl. Do not point it at a system font.",
        )
    queries = {
        "bold": ("Poppins:weight=bold", font_file("bold")),
        "mono": ("JetBrains Mono:weight=regular", font_file("mono")),
    }
    bundled = {font_file(key).resolve() for key in spec["fonts"]["family"]}
    for key, (query, expected) in queries.items():
        resolved = _fc_match(query)
        if Path(resolved).name != expected.name:
            raise LayoutError(
                "fonts", "R09",
                f"fontconfig resolved {query} to {resolved}, not {expected.name}",
                "Fix fonts.conf so this family cannot fall back to a system font.",
            )
    # A generic Poppins lookup must stay inside the bundle. The catch-all file is Bold.
    generic = Path(_fc_match("Poppins")).resolve()
    if generic not in bundled:
        raise LayoutError(
            "fonts", "R09",
            f"fontconfig resolved Poppins to {generic}, outside the bundled fonts",
            "Fix fonts.conf so Poppins cannot fall back to a system font.",
        )
