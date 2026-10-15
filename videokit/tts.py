#!/usr/bin/env python3
"""Shared local neural TTS (Piper).

Runs fully offline: no cloud service, no API key. Synthesises one sentence at a
time, normalises each take to a fixed LUFS so sentence-to-sentence level is
even, and resamples to the 48 kHz project rate.

Results are content-addressed and cached on disk, so a rebuild that does not
change the script costs nothing.
"""
from __future__ import annotations

import hashlib
import json
import wave
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

TARGET_SR = 48000
SENTENCE_LUFS = -18.0
LENGTH_SCALE = 1.05
LENGTH_SCALE_RANGE = (0.98, 1.10)


@dataclass
class Take:
    audio: np.ndarray                 # float32 mono at TARGET_SR
    duration: float
    sample_rate: int = TARGET_SR
    length_scale: float = LENGTH_SCALE
    noise_scale: float | None = None
    noise_w: float | None = None
    lufs: float = 0.0
    attempt: int = 0
    notes: list[str] = field(default_factory=list)


def _resample(x: np.ndarray, src: int, dst: int = TARGET_SR) -> np.ndarray:
    if src == dst:
        return x.astype(np.float32)
    from math import gcd

    from scipy.signal import resample_poly

    g = gcd(int(src), int(dst))
    return resample_poly(x.astype(np.float32), dst // g, src // g).astype(np.float32)


def _normalise_lufs(x: np.ndarray, target: float = SENTENCE_LUFS,
                    sr: int = TARGET_SR) -> tuple[np.ndarray, float]:
    import pyloudnorm

    m = pyloudnorm.Meter(sr)
    loud = m.integrated_loudness(x.astype(np.float64))
    if not np.isfinite(loud) or loud < -65.0:
        # too quiet or near-silent to measure: keep the take, just trim peaks
        peak = float(np.abs(x).max()) or 1.0
        y = x / peak * 0.89
        return y.astype(np.float32), -65.0
    gain = float(10.0 ** ((target - loud) / 20.0))
    y = x * gain
    peak = float(np.abs(y).max())
    if peak > 0.97:                      # never clip after gain
        y *= 0.97 / peak
    return y.astype(np.float32), float(loud)


class Piper:
    """Thin wrapper matching the installed piper-tts API."""

    def __init__(self, model: Path, cache_dir: Path | None = None):
        from piper import PiperVoice

        self.model = Path(model)
        if not self.model.is_file():
            raise FileNotFoundError(f"Piper voice model missing: {model}")
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.voice = PiperVoice.load(str(self.model))
        self.sample_rate = int(self.voice.config.sample_rate)

    # ------------------------------------------------------------------ core
    def _synth_raw(self, text: str, length_scale: float,
                   noise_scale: float | None, noise_w: float | None) -> np.ndarray:
        from piper import SynthesisConfig

        kw = {"length_scale": float(length_scale)}
        if noise_scale is not None:
            kw["noise_scale"] = float(noise_scale)
        if noise_w is not None:
            # piper-tts 1.x names this noise_w_scale
            kw["noise_w_scale"] = float(noise_w)
        cfg = SynthesisConfig(**kw)
        chunks = [np.asarray(c.audio_float_array, dtype=np.float32)
                  for c in self.voice.synthesize(text, cfg)]
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks)

    def say(self, text: str, length_scale: float = LENGTH_SCALE,
            noise_scale: float | None = None, noise_w: float | None = None,
            attempt: int = 0, use_cache: bool = True) -> Take:
        text = " ".join(str(text).split())
        if not text:
            raise ValueError("empty text")
        key = hashlib.sha256(
            f"{self.model.name}|{self.sample_rate}|{text}|{length_scale:.4f}"
            f"|{noise_scale}|{noise_w}".encode()).hexdigest()[:32]
        wav_path = (self.cache_dir / f"{key}.wav") if self.cache_dir else None
        meta_path = (self.cache_dir / f"{key}.json") if self.cache_dir else None

        if use_cache and wav_path and wav_path.is_file() and meta_path and meta_path.is_file():
            with wave.open(str(wav_path), "rb") as w:
                raw = w.readframes(w.getnframes())
            a = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            return Take(a, len(a) / TARGET_SR, TARGET_SR, meta.get("length_scale", length_scale),
                        noise_scale, noise_w, meta.get("lufs", 0.0), attempt)

        raw = self._synth_raw(text, length_scale, noise_scale, noise_w)
        if raw.size == 0:
            raise RuntimeError(f"Piper produced no audio for: {text[:60]!r}")
        a = _resample(raw, self.sample_rate, TARGET_SR)
        a, lufs = _normalise_lufs(a, SENTENCE_LUFS, TARGET_SR)

        if wav_path:
            with wave.open(str(wav_path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(TARGET_SR)
                w.writeframes((np.clip(a, -1, 1) * 32767).astype("<i2").tobytes())
            meta_path.write_text(json.dumps({"length_scale": length_scale, "lufs": lufs,
                                             "text": text}), encoding="utf-8")
        return Take(a, len(a) / TARGET_SR, TARGET_SR, length_scale,
                    noise_scale, noise_w, lufs, attempt)

    # ------------------------------------------------------------------ helpers
    def fit_length_scale(self, text: str, target_seconds: float,
                         lo: float = LENGTH_SCALE_RANGE[0],
                         hi: float = LENGTH_SCALE_RANGE[1]) -> Take:
        """Nudge length_scale inside the allowed band to land near a target duration."""
        best = self.say(text, LENGTH_SCALE)
        for _ in range(3):
            if abs(best.duration - target_seconds) <= 0.12:
                break
            ratio = best.duration / max(target_seconds, 1e-3)
            cand = min(hi, max(lo, LENGTH_SCALE * ratio))
            if abs(cand - LENGTH_SCALE) < 0.005:
                break
            trial = self.say(text, cand)
            if abs(trial.duration - target_seconds) < abs(best.duration - target_seconds):
                best = trial
            else:
                break
        return best