"""AST lint. Scene modules may not carry coordinates or call cairo."""
from __future__ import annotations

import ast
import os
from pathlib import Path

from layout.spec import ABIT, load_spec

DRAW_CALLS = {
    "show_text", "set_font_size", "move_to", "line_to", "rectangle",
    "arc", "select_font_face", "set_source_rgba",
}


def lint_sources() -> list[str]:
    spec = load_spec()
    legacy = set(spec["legacy_roots"])
    allowed = {ABIT / item for item in spec["lint_draw_modules"]}
    problems = []
    skip_dirs = {".venv", ".cache", "tools", "__pycache__", "tests"}
    roots = [ABIT / "layout", ABIT / "examples"]
    reserved = {
        "layout", "examples", "pipeline", "assets", "docs", "prompts", "tests",
        "tools", ".venv", ".cache", ".git",
    }
    for child in ABIT.iterdir():
        if child.is_dir() and child.name not in reserved and child.name not in legacy:
            roots.append(child)
    for root in roots:
        if not root.is_dir():
            continue
        _scan(root, spec, legacy, allowed, problems, skip_dirs)
    return problems


def _scan(root: Path, spec, legacy: set[str], allowed: set[Path], problems: list[str], skip_dirs: set[str]) -> None:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in skip_dirs and name not in legacy]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            path = Path(dirpath) / filename
            rel = path.relative_to(ABIT).as_posix()
            if rel.split("/")[0] in legacy:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            if path.resolve() not in {item.resolve() for item in allowed}:
                problems.extend(_drawing(rel, tree))
            if rel.startswith("examples/") or rel.endswith("scenes.py"):
                problems.extend(_literals(rel, tree))
    return problems


def _drawing(rel: str, tree: ast.AST) -> list[str]:
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "cairo":
                    found.append(f"{rel}:{node.lineno}: cairo import outside the renderer")
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "cairo":
            found.append(f"{rel}:{node.lineno}: cairo import outside the renderer")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in DRAW_CALLS:
            found.append(f"{rel}:{node.lineno}: {node.func.attr} bypasses the layout renderer")
    return found


def _literals(rel: str, tree: ast.AST) -> list[str]:
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, (int, float)):
            continue
        for target in node.targets:
            name = target.id if isinstance(target, ast.Name) else ""
            if name in {"x", "y", "w", "h", "font_size", "size"}:
                found.append(f"{rel}:{node.lineno}: coordinate or font size {name} = {node.value.value}")
    return found
