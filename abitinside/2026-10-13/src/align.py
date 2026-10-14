#!/usr/bin/env python3
"""
A Bit Inside - word timing for burned-in captions (section 7.4).

Runs faster-whisper (offline, int8) over each synthesised sentence to get
word-level timestamps. If a word is missing or the confidence is low, that
sentence falls back to character-weighted proportional timing inside the
sentence's own measured duration, so a caption never lands outside its scene.

Writes align.json.
"""
from __future__ import annotations

import json
import os
import re
import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DAY = HERE.parent
sys.path.insert(0, str(HERE))

SR = 22050
FPS = 30
MODEL = "base.en"
MIN_AVG_CONF = 0.45             # faster-whisper word probability, 0..1
MIN_WORD_COUNT_RATIO = 0.75     # whisper must return at least this share of words

CAPTION_WORDS = (2, 3)          # words per caption group (spec: 2-4)
CAPTION_MAX_PX = 800           # Poppins Bold at 72 px, inside the 840 px safe zone
FONT_PATH = None               # filled in main()
NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "hundred": 100, "thousand": 1000,
}
CYAN_HINTS = {"fridge", "fridges", "controller", "controllers", "box", "web",
              "interface", "page", "cases", "defrost", "cert", "alert", "stores",
              "trace", "flaw", "flaws", "login", "password", "code"}


def tokenise(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9'\.\-]*", text)


def write_wav(path: Path, x: np.ndarray) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def proportional(text: str, duration: float, lead: float = 0.02) -> list[dict]:
    """Character-weighted fallback inside one sentence."""
    toks = tokenise(text)
    if not toks:
        return []
    weights = [max(1, len(t)) + (2 if t.endswith((".", ",", "?")) else 0) for t in toks]
    total = float(sum(weights))
    out = []
    t = lead
    for tok, w in zip(toks, weights):
        d = duration * w / total
        out.append({"word": tok, "t_start": round(t, 3), "t_end": round(t + d, 3),
                    "conf": 0.0, "source": "proportional"})
        t += d
    return out


def snap_to_script(words: list[dict], tokens: list[str]) -> list[dict] | None:
    """Keep Whisper's TIMINGS but use the script's SPELLING.

    Whisper occasionally returns the wrong word for the same audio ("gerated" for
    "generated"). Those timings are still correct, but the caption is burned into
    the picture, so the text must come from the script. When the token counts match
    and the pairs are similar enough, each timing is re-attached to the script
    token. Otherwise the caller falls back to proportional timing.
    """
    from difflib import SequenceMatcher

    if len(words) != len(tokens) or not tokens:
        return None
    ratios = []
    out = []
    for w, tok in zip(words, tokens):
        a = re.sub(r"[^a-z0-9]", "", w["word"].lower())
        b = re.sub(r"[^a-z0-9]", "", tok.lower())
        r = SequenceMatcher(None, a, b).ratio()
        ratios.append(r)
        out.append({**w, "word": tok, "asr_word": w["word"], "match": round(r, 2)})
    if sum(ratios) / len(ratios) < 0.55:
        return None
    return out


def align_sentences(model, sentences: list[dict], tmp: Path) -> list[dict]:
    import soundfile as sf

    raw, sr = sf.read(str(DAY / "audio" / "narration_22050.wav"), dtype="float32")
    out = []
    for i, s in enumerate(sentences):
        a = int(s["start_sample"])
        b = a + int(s["samples"] * (SR / sr))
        clip = raw[a:b]
        p = tmp / f"s{i:03d}.wav"
        write_wav(p, clip)
        segs, info = model.transcribe(str(p), language="en", word_timestamps=True,
                                      beam_size=1, vad_filter=False, condition_on_previous_text=False)
        words = []
        for seg in segs:
            for w in (seg.words or []):
                tok = re.sub(r"[^A-Za-z0-9'\.\-]", "", w.word)
                if not tok:
                    continue
                words.append({"word": tok, "t_start": round(w.start, 3),
                              "t_end": round(w.end, 3),
                              "conf": round(float(w.probability), 3),
                              "source": "whisper"})
        expected = tokenise(s["text"])
        avg_conf = float(np.mean([w["conf"] for w in words])) if words else 0.0
        ratio = len(words) / max(1, len(expected))
        snapped = snap_to_script(words, expected) if words else None
        good = (ratio >= MIN_WORD_COUNT_RATIO and avg_conf >= MIN_AVG_CONF
                and words[0]["t_start"] < 0.9 and words[-1]["t_end"] > 0.05
                and snapped is not None)
        if good:
            words = snapped
            fixed = [w for w in words if w["match"] < 1.0]
            reason = (f"whisper timings, {len(words)} words, avg confidence {avg_conf:.2f}"
                      + (f", {len(fixed)} re-spelled from the script" if fixed else ""))
        else:
            words = proportional(s["text"], s["seconds"])
            reason = (f"fallback (whisper returned {len(words)}/{len(expected)} words, "
                      f"avg confidence {avg_conf:.2f}"
                      + (", token mismatch)" if snapped is None else ")"))
        for w in words:
            w["t_global"] = round(s["start_seconds"] + w["t_start"], 3)
            w["frame"] = int(round(w["t_global"] * FPS))
        out.append({**{k: v for k, v in s.items()},
                    "words": words, "align_method": reason,
                    "expected_words": len(expected)})
        p.unlink(missing_ok=True)
        print(f"  s{i:02d} {s['scene']:<12} {len(words):>2}/{len(expected):<2} words  {reason}")
    return out


def pick_accent(group: list[str], sentence: str, cyan_words: list[str]) -> tuple[str, str]:
    """Longest word in the group is the key word; cyan if it is a subject word."""
    cy = {c.lower() for c in cyan_words}
    best = max(group, key=lambda w: (len(w) > 3, len(w)))
    low = best.lower()
    if low in cy or low in CYAN_HINTS:
        return best, "cyan"
    return best, "yellow"


_MEASURE = None


def measure_px(text: str) -> float:
    """Width of a caption group in Poppins Bold at caption size."""
    global _MEASURE
    if _MEASURE is None:
        from PIL import ImageFont

        f = str(Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"
                / "Poppins-Bold.ttf")
        _MEASURE = ImageFont.truetype(f, 100)
    return _MEASURE.getlength(text) / 100.0 * 72.0


def build_captions(aligned: list[dict], cyan_by_scene: dict[str, list[str]]) -> list[dict]:
    caps = []
    for s in aligned:
        words = s["words"]
        if not words:
            continue
        cy = {c.lower() for c in cyan_by_scene.get(s["scene"], [])}
        sentence_lower = s["text"].lower()
        i = 0
        while i < len(words):
            n = 1
            for k in CAPTION_WORDS:
                if i + k > len(words):
                    continue
                cand = words[i:i + k]
                joined = " ".join(w["word"] for w in cand)
                if len(cand) >= CAPTION_WORDS[0] and measure_px(joined) <= CAPTION_MAX_PX:
                    n = k
                    break
            n = max(1, min(n, len(words) - i))
            group = words[i:i + n]
            # never split a hyphenated token across two caption groups
            while n > 1 and group[-1]["word"].endswith("-") and i + n < len(words):
                n -= 1
                group = words[i:i + n]
            texts = [w["word"] for w in group]
            key, accent = pick_accent(texts, sentence_lower, cy)
            caps.append({
                "scene": s["scene"],
                "text": " ".join(texts).strip(" ,.;:!?"),
                "key": key,
                "accent": accent,
                "frame": group[0]["frame"],
                "end_frame": group[-1]["frame"] + 2,
                "width_px": round(measure_px(" ".join(texts)), 1),
            })
            i += n
    return caps


def main() -> int:
    tmp = DAY / ".cache" / "align"
    tmp.mkdir(parents=True, exist_ok=True)
    tts = json.loads((DAY / "tts_sentences.json").read_text(encoding="utf-8"))
    plan = json.loads((DAY / "scenes_plan.json").read_text(encoding="utf-8"))
    cyan_by_scene = {s["id"]: s.get("cyan", []) for s in plan["scenes"]}

    os.environ.setdefault("HF_HOME", str(ABIT_CACHE := (DAY.parent / ".cache" / "huggingface")))
    from faster_whisper import WhisperModel

    print(f"loading faster-whisper {MODEL} (int8, cpu)")
    model = WhisperModel(MODEL, device="cpu", compute_type="int8",
                         download_root=str(DAY.parent / ".cache" / "huggingface"),
                         cpu_threads=2)
    print(f"aligning {len(tts['sentences'])} sentences")
    aligned = align_sentences(model, tts["sentences"], tmp)
    caps = build_captions(aligned, cyan_by_scene)

    n_fb = sum(1 for s in aligned if s["align_method"].startswith("fallback"))
    widest = max((c.get("width_px", 0) for c in caps), default=0)
    out = {
        "model": MODEL,
        "fps": FPS,
        "sentences": aligned,
        "captions": caps,
        "fallback_sentences": n_fb,
        "caption_groups": len(caps),
        "max_group_words": max(len(c["text"].split()) for c in caps),
        "widest_group_px": widest,
        "caption_max_px": CAPTION_MAX_PX,
    }
    (DAY / "align.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"\ncaptions: {len(caps)} groups, longest {out['max_group_words']} words, "
          f"widest {widest:.0f} px (limit {CAPTION_MAX_PX}), "
          f"{n_fb} sentences used proportional fallback")
    print("wrote align.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())