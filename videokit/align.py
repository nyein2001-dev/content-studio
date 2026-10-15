#!/usr/bin/env python3
"""Shared caption alignment with faster-whisper.

Whisper supplies the TIMINGS; the script supplies the SPELLING. Each recognised
token is snapped to the nearest script word by sequence similarity, so a caption
never disagrees with the narration while still switching on the real word edge.

If whisper cannot load or returns nothing usable, a character-weighted
proportional fallback keeps the build running with the correct total duration.
"""
from __future__ import annotations

import difflib
import json
from pathlib import Path

import numpy as np

SR = 48000
ALIGN_SR = 22050
MODEL_SMALL = "base.en"
DEFAULT_MODEL = "base.en"


class Aligner:
    def __init__(self, model_name: str = DEFAULT_MODEL, download_root: str | None = None,
                 device: str = "cpu", compute_type: str = "int8"):
        from faster_whisper import WhisperModel

        self.model = WhisperModel(model_name, device=device, compute_type=compute_type,
                                  download_root=download_root)
        self.model_name = model_name
        self.used_fallback = False

    # ------------------------------------------------------------------ tokens
    @staticmethod
    def _tokens(script_text: str) -> list[str]:
        import re
        return re.findall(r"[A-Za-z0-9$%€£'’\-\.,]+", script_text)

    def align(self, wav_path: Path, sentences: list[dict]) -> dict:
        """sentences: [{id, text, start_seconds, end_seconds}, ...]

        Returns {clock, words, groups} where words carry start/end seconds.
        """
        segs, info = self.model.transcribe(
            str(wav_path), language="en", word_timestamps=True, beam_size=5,
            vad_filter=False, condition_on_previous_text=False)
        heard: list[tuple[float, float, str]] = []
        for s in segs:
            for w in (s.words or []):
                t = w.word.strip()
                if t:
                    heard.append((float(w.start), float(w.end), t))
        if not heard:
            self.used_fallback = True
            return self._fallback(sentences)

        words = self._snap(sentences, heard)
        return {"clock": f"faster-whisper:{self.model_name}", "words": words,
                "groups": self._group(words), "fallback": False}

    def _snap(self, sentences: list[dict], heard: list[tuple[float, float, str]]) -> list[dict]:
        """Assign each script word the timing of its best-matching heard token."""
        out: list[dict] = []
        cursor = 0
        for sent in sentences:
            script = self._tokens(sent["text"])
            sid = sent.get("id") or f'{sent.get("scene", "s")}:{sent.get("index", 0)}'
            for word in script:
                best_i, best_s = -1, 0.0
                span = range(max(0, cursor - 3), min(len(heard), cursor + 12))
                for i in span:
                    s = difflib.SequenceMatcher(
                        None, word.lower().strip(".,'-"), heard[i][2].lower().strip(".,'-")).ratio()
                    if s > best_s:
                        best_i, best_s = i, s
                if best_i >= 0 and best_s >= 0.45:
                    cursor = best_i
                    start, end = heard[best_i][0], heard[best_i][1]
                else:
                    # proportional fallback inside this sentence
                    i = min(max(0, cursor), max(0, len(heard) - 1))
                    start, end = heard[i][0], heard[i][1]
                out.append({"text": word, "sentence": sid,
                            "start": float(start), "end": float(end), "match": float(best_s)})
        return out

    @staticmethod
    def _group(words: list[dict], max_words: int = 4, gap_s: float = 0.34) -> list[dict]:
        """Chunk words into caption groups of 3-5 words, never leaving a lone last word."""
        groups: list[dict] = []
        cur: list[dict] = []
        for w in words:
            if cur and (len(cur) >= max_words or (w["start"] - cur[-1]["end"]) > gap_s):
                groups.append({"words": cur, "start": cur[0]["start"], "end": cur[-1]["end"]})
                cur = []
            cur.append(w)
        if cur:
            if groups and len(cur) == 1 and len(groups[-1]["words"]) > 1:
                groups[-1]["words"].extend(cur)
                groups[-1]["end"] = groups[-1]["words"][-1]["end"]
            else:
                groups.append({"words": cur, "start": cur[0]["start"], "end": cur[-1]["end"]})
        for g in groups:
            g["text"] = " ".join(w["text"] for w in g["words"])
        return groups

    @staticmethod
    def _fallback(sentences: list[dict]) -> dict:
        words: list[dict] = []
        for sent in sentences:
            toks = Aligner._tokens(sent["text"])
            if not toks:
                continue
            total = sum(len(t) + 1 for t in toks) or 1
            t = sent["start_seconds"]
            dur = max(0.15, sent["end_seconds"] - sent["start_seconds"])
            for tok in toks:
                share = (len(tok) + 1) / total * dur
                words.append({"text": tok, "sentence": sent["id"], "start": t,
                              "end": t + share, "match": 0.0})
                t += share
        return {"clock": "proportional-fallback", "words": words,
                "groups": Aligner._group(words), "fallback": True}


def transcribe_for_check(mp4_or_wav: Path, model_name: str = "small.en",
                         download_root: str | None = None) -> str:
    """Full transcript of a finished file, for the ASR gate."""
    from faster_whisper import WhisperModel

    m = WhisperModel(model_name, device="cpu", compute_type="int8", download_root=download_root)
    segs, _ = m.transcribe(str(mp4_or_wav), language="en", beam_size=5,
                           condition_on_previous_text=False)
    return " ".join(s.text.strip() for s in segs)