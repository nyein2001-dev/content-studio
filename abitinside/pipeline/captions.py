"""Caption groups built from the narration, with real spaces and real end times.

The clock is the TTS word boundary. A caption starts when its first word starts
and stays up until its last word has finished. Punctuation stays on its word.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import CAPTION_MAX_PX, CAPTION_MAX_WORDS, FPS, ROOT  # noqa: E402

INK = "#F4F7FB"
ACCENT = "#EABF40"


def _font():
    from PIL import ImageFont

    return ImageFont.truetype(str(ROOT / "assets" / "fonts" / "Poppins-Bold.ttf"), 72)


_FONT = None


def text_width(text: str) -> float:
    global _FONT
    if _FONT is None:
        _FONT = _font()
    return float(_FONT.getlength(text))


def visible_runs(group: dict, frame: float,
                 ink: str = INK, accent: str = ACCENT) -> tuple[list | None, float]:
    """Runs for the caption at this frame, including a space token between words.

    The accent colour is applied only to the word whose spoken interval contains
    the frame. Returns (None, 0) when the caption is not on screen.
    """
    start = group["frame"]
    end = group["end_frame"]
    if not (start <= frame < end):
        return None, 0.0
    t = min(1.0, max(0.0, (frame - start) / 5.0))
    ease = 1.0 - (1.0 - t) ** 3
    words = group.get("words")
    if not words:
        words = [{"text": part, "frame": start, "end_frame": end}
                 for part in group["text"].split(" ") if part]
    runs: list[tuple[str, str]] = []
    for i, word in enumerate(words):
        spoken = word["frame"] <= frame < word["end_frame"]
        runs.append((word["text"], accent if spoken else ink))
        if i < len(words) - 1:
            runs.append((" ", ink))
    return runs, ease


def _break_here(words: list[dict], count: int) -> bool:
    if count >= CAPTION_MAX_WORDS:
        return True
    token = words[count - 1]["text"]
    if count >= 3 and token.endswith((".", "?", "!", ",", ";", ":")):
        return True
    return False


def build_groups(sentences: list[dict]) -> list[dict]:
    """Group timed words into readable lines. Times are absolute seconds."""
    groups: list[dict] = []
    for sentence in sentences:
        words = sentence.get("words") or []
        if not words:
            continue
        origin = float(sentence["start_seconds"])
        absolute = []
        for word in words:
            text = str(word["text"]).strip()
            if not text:
                continue
            absolute.append({
                "text": text,
                "t0": origin + float(word["t_start"]),
                "t1": origin + float(word["t_end"]),
            })
        i = 0
        while i < len(absolute):
            count = 1
            while i + count < len(absolute) and count < CAPTION_MAX_WORDS:
                trial = absolute[i:i + count + 1]
                joined = " ".join(w["text"] for w in trial)
                if text_width(joined) > CAPTION_MAX_PX:
                    break
                count += 1
                if _break_here(trial, count):
                    break
            chunk = absolute[i:i + count]
            text = " ".join(w["text"] for w in chunk)
            frame = int(round(chunk[0]["t0"] * FPS))
            end_frame = int(round(chunk[-1]["t1"] * FPS))
            if end_frame <= frame:
                end_frame = frame + max(2, int(round((chunk[-1]["t1"] - chunk[0]["t0"]) * FPS)))
            timed = [{
                "text": w["text"],
                "frame": int(round(w["t0"] * FPS)),
                "end_frame": max(int(round(w["t1"] * FPS)), int(round(w["t0"] * FPS)) + 1),
            } for w in chunk]
            groups.append({
                "scene": sentence["scene"],
                "text": text,
                "key": timed[-1]["text"].strip(".,;:!?"),
                "accent": "yellow",
                "frame": frame,
                "end_frame": end_frame,
                "words": timed,
                "width_px": round(text_width(text), 1),
            })
            i += count
    for earlier, later in zip(groups, groups[1:]):
        if earlier["end_frame"] > later["frame"]:
            earlier["end_frame"] = later["frame"]
    return groups


def write_align(day: Path) -> Path:
    tts = json.loads((day / "tts_sentences.json").read_text(encoding="utf-8"))
    if tts.get("voice") != "en-US-AndrewNeural":
        raise SystemExit(f"refusing to caption audio from voice {tts.get('voice')!r}")
    groups = build_groups(tts["sentences"])
    for group in groups:
        if " " not in group["text"] and len(group["words"]) > 1:
            raise SystemExit(f"caption lost its spaces: {group['text']!r}")
        last = group["words"][-1]["end_frame"]
        if group["end_frame"] < last:
            raise SystemExit(
                f"caption {group['text']!r} ends at frame {group['end_frame']} "
                f"before its last word ends at {last}"
            )
    sentences = []
    for sentence in tts["sentences"]:
        sentences.append({
            "scene": sentence["scene"],
            "text": sentence["text"],
            "start_seconds": sentence["start_seconds"],
            "seconds": sentence["seconds"],
            "words": sentence.get("words", []),
            "align_method": "edge-tts-word-boundary",
        })
    out = {
        "clock": "edge-tts-word-boundary",
        "voice": tts["voice"],
        "fps": FPS,
        "sentences": sentences,
        "captions": groups,
        "caption_groups": len(groups),
        "max_group_words": max((len(c["words"]) for c in groups), default=0),
        "widest_group_px": max((c["width_px"] for c in groups), default=0),
    }
    path = day / "align.json"
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"captions: {len(groups)} groups, clock {out['clock']}")
    return path


def main(argv: list[str] | None = None) -> int:
    day = Path(sys.argv[1] if argv is None else argv[0]).resolve()
    write_align(day)
    return 0


if __name__ == "__main__":
    sys.exit(main())
