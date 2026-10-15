#!/usr/bin/env python3
"""Automatic per-sentence voice QA for local neural narration.

Four flags, all measurable from the rendered take alone:

  FLAT   pitch standard deviation < 1.8 semitones on a sentence of >= 8 words
  RUSH   speaking rate > 190 words per minute
  LOW    mean level more than 6 dB below the take median
  DRONE  >= 25 words with no internal pause longer than 120 ms

For every flag the caller re-synthesises (splitting at a clause or nudging the
sampler) and keeps the best version. Anything still flagged is reported, never
silently dropped.
"""
from __future__ import annotations

import re

import numpy as np

SR = 48000
FLAT_SEMITONES = 1.8
FLAT_MIN_WORDS = 8
RUSH_WPM = 190.0
LOW_DB_BELOW = 6.0
DRONE_MIN_WORDS = 25
DRONE_PAUSE_S = 0.12
DRONE_GAP_S = 0.35          # only gaps at least this long count as "internal"

_CLAUSE = re.compile(r"(?<=[,;:])\s+(?=[A-Z0-9])|\s+—\s+|\s+-\s+(?=[A-Z0-9])")


def word_count(text: str) -> int:
    return len([w for w in re.split(r"\s+", text.strip()) if w])


def speaking_rate(text: str, duration: float) -> float:
    if duration <= 0:
        return 0.0
    return word_count(text) / duration * 60.0


def pitch_semitone_sd(x: np.ndarray, sr: int = SR) -> float:
    """Track F0 with autocorrelation per frame and return the spread in semitones."""
    if x.size < sr // 4:
        return 0.0
    win = int(sr * 0.04)
    hop = int(sr * 0.02)
    lo, hi = int(sr / 400.0), int(sr / 70.0)      # 70..400 Hz
    f0 = []
    m = x.astype(np.float32) - np.float32(x.mean())
    for i in range(0, max(1, len(m) - win), hop):
        seg = m[i:i + win]
        if np.sqrt(float((seg * seg).mean())) < 1e-3:
            continue
        seg = seg * np.hanning(win)
        corr = np.correlate(seg, seg, mode="full")[win - 1:]
        if corr[0] <= 1e-9:
            continue
        corr[:lo] = 0
        band = corr[lo:hi]
        if band.size == 0:
            continue
        k = int(np.argmax(band)) + lo
        ref = float(corr[0])
        if ref <= 1e-9 or corr[k] / ref < 0.32:
            continue
        f0.append(sr / k)
    if len(f0) < 8:
        return 0.0
    f0 = np.asarray(f0, dtype=np.float64)
    f0 = f0[(f0 > 60) & (f0 < 450)]
    if f0.size < 8:
        return 0.0
    semis = 12.0 * np.log2(np.clip(f0, 1e-6, None) / float(np.median(f0)))
    return float(np.std(semis))


def level_dbfs(x: np.ndarray) -> float:
    if x.size == 0:
        return -120.0
    return float(20.0 * np.log10(max(1e-9, float(np.sqrt((x.astype(np.float64) ** 2).mean())))))


def longest_pause(x: np.ndarray, sr: int = SR, gate_db: float = -42.0,
                  rms_win_s: float = 0.02) -> float:
    """Longest interior run quieter than `gate_db`; returns seconds."""
    w = max(1, int(sr * rms_win_s))
    n = len(x) // w
    if n < 3:
        return 0.0
    fr = x[:n * w].astype(np.float64).reshape(n, w)
    rms = np.sqrt((fr ** 2).mean(axis=1)) + 1e-12
    db = 20 * np.log10(rms)
    quiet = db < gate_db
    best = run = 0
    for q in quiet:
        run = run + 1 if q else 0
        best = max(best, run)
    return best * rms_win_s


def check(text: str, audio: np.ndarray, duration: float, take_median_dbfs: float,
          sr: int = SR) -> list[str]:
    """Return the list of flag names raised for one sentence (may be empty)."""
    flags: list[str] = []
    n = word_count(text)
    if n >= FLAT_MIN_WORDS and pitch_semitone_sd(audio, sr) < FLAT_SEMITONES:
        flags.append("FLAT")
    if speaking_rate(text, duration) > RUSH_WPM:
        flags.append("RUSH")
    if take_median_dbfs - level_dbfs(audio) > LOW_DB_BELOW:
        flags.append("LOW")
    if n >= DRONE_MIN_WORDS and longest_pause(audio, sr) >= DRONE_GAP_S:
        flags.append("DRONE")
    return flags


def score(text: str, audio: np.ndarray, duration: float, sr: int = SR) -> float:
    """Lower is better. Used to pick between re-synthesised takes."""
    n = max(1, word_count(text))
    sd = pitch_semitone_sd(audio, sr)
    wpm = speaking_rate(text, duration)
    return (abs(sd - 4.5) / 4.5) + (abs(wpm - 158.0) / 158.0) + (0.35 / n)


def split_for_retry(text: str) -> list[str]:
    """Natural clause boundaries, longest part first."""
    parts = [p.strip() for p in _CLAUSE.split(text) if p and p.strip()]
    if len(parts) < 2:
        words = text.split()
        if len(words) > 6:
            mid = len(words) // 2
            return [" ".join(words[:mid]), " ".join(words[mid:])]
        return []
    parts.sort(key=len, reverse=True)
    return parts


def retry_variants(text: str) -> list[dict]:
    """Up to 3 distinct ways to re-synthesise a flagged sentence."""
    out: list[dict] = []
    for ns, nw in ((0.667, 0.8), (0.733, 0.9)):
        out.append({"noise_scale": ns, "noise_w": nw, "how": f"noise_scale={ns}, noise_w={nw}"})
    parts = split_for_retry(text)
    if len(parts) >= 2:
        out.append({"noise_scale": 0.667, "noise_w": 0.8, "how": f"clause split {len(parts)} parts"})
    return out[:3]