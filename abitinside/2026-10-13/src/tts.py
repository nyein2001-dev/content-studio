#!/usr/bin/env python3
"""
A Bit Inside - offline neural narration (section 7.2).

Synthesises the script sentence by sentence with Piper, measures each sentence's
real duration, normalises every sentence to -16 LUFS, trims the tails, and writes:

    tts_sentences.json  - per-sentence sample counts, start samples, LUFS
    audio/narration.wav - the continuous narration track with the designed pauses

Scene lengths are set by these measured durations, never by an estimate. If the
total lands outside the target runtime, length_scale is nudged inside the allowed
0.95-1.08 window and the whole pass is repeated. Speech is never time-stretched.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
import soundfile as sf

HERE = Path(__file__).resolve().parent
DAY = HERE.parent
ABIT = DAY.parent
sys.path.insert(0, str(HERE))

from piper import PiperVoice, SynthesisConfig  # noqa: E402

SR = 22050                     # en_US-ryan-high native rate
TARGET_SR = 48000              # everything downstream is 48 kHz
SENTENCE_LUFS = -16.0
METER = pyln.Meter(SR)

# Designed gaps, in seconds. Longer before the reveal, tighter elsewhere.
GAP_AFTER_DEFAULT = 0.30
GAP_BEFORE_REVEAL = 0.62      # before the payoff scene
GAP_BEFORE_ENDCARD = 0.45
# A short lead-in before the first word. This exists for the loop: the final frame
# is a verbatim copy of frame 0, so frame 0 must carry no caption, and the first
# caption group has to start on or after frame 4. Shifting the audio and the
# alignment together keeps caption-to-speech sync exact.
LEAD_IN_FRAMES = 4
LEAD_IN_S = LEAD_IN_FRAMES / 30.0

TARGET_MIN_S, TARGET_MAX_S = 100.0, 135.0


def voice_path() -> Path:
    voices = sorted((ABIT / "assets" / "voices").glob("*.onnx"))
    if not voices:
        raise SystemExit("no Piper voice found in assets/voices - run setup.sh")
    preferred = [v for v in voices if "ryan-high" in v.name]
    return (preferred or voices)[0]


def load_voice():
    print(f"loading voice {voice_path().name}")
    return PiperVoice.load(str(voice_path()))


def synth(voice, text: str, length_scale: float) -> np.ndarray:
    chunks = list(voice.synthesize(text, syn_config=SynthesisConfig(
        length_scale=length_scale, noise_scale=0.667, noise_w_scale=0.8,
        volume=1.0, normalize_audio=True)))
    if not chunks:
        raise RuntimeError(f"piper returned nothing for: {text[:50]}")
    audio = np.concatenate([c.audio_int16_array for c in chunks]).astype(np.float32)
    return audio / 32768.0


def trim_silence(x: np.ndarray, thresh: float = 0.004) -> np.ndarray:
    idx = np.where(np.abs(x) > thresh)[0]
    if not len(idx):
        return x
    a = max(0, idx[0] - int(0.01 * SR))
    b = min(len(x), idx[-1] + int(0.06 * SR))
    return x[a:b]


def highpass(x: np.ndarray, fc: float = 80.0) -> np.ndarray:
    """Gentle high-pass so phone speakers still carry the voice."""
    from scipy.signal import butter, sosfilt

    sos = butter(2, fc / (SR / 2), btype="highpass", output="sos")
    return sosfilt(sos, x).astype(np.float32)


def presence(x: np.ndarray) -> np.ndarray:
    """Light presence lift around 2-4 kHz and a touch of de-ess around 6 kHz."""
    from scipy.signal import butter, sosfilt

    ny = SR / 2
    boost = butter(2, [2200 / ny, 4200 / ny], btype="bandpass", output="sos")
    cut = butter(2, [5200 / ny, 9000 / ny], btype="bandpass", output="sos")
    y = x + 0.22 * sosfilt(boost, x) - 0.16 * sosfilt(cut, x)
    return y.astype(np.float32)


def normalise_lufs(x: np.ndarray, target: float = SENTENCE_LUFS) -> tuple[np.ndarray, float]:
    m = pyln.Meter(SR)
    loud = m.integrated_loudness(x.astype(np.float64))
    if not np.isfinite(loud):
        return x, -99.0
    gain = 10 ** ((target - loud) / 20)
    y = x * gain
    peak = float(np.max(np.abs(y)))
    ceiling = 10 ** (-3.0 / 20)       # leave headroom for presence EQ and the master sum
    if peak > ceiling:
        y = y * (ceiling / peak)
    return y.astype(np.float32), loud


def run_pass(voice, lines, length_scale: float):
    out = []
    for scene_id, idx, text in lines:
        raw = trim_silence(synth(voice, text, length_scale))
        y, loud = normalise_lufs(raw)
        y = presence(highpass(y))
        out.append({
            "scene": scene_id,
            "index": idx,
            "text": text,
            "length_scale": round(length_scale, 4),
            "samples": int(y.size),
            "seconds": round(y.size / SR, 3),
            "lufs_before": round(loud, 2),
            "audio": y,
        })
    return out


def main() -> int:
    plan = json.loads((DAY / "scenes_plan.json").read_text(encoding="utf-8"))
    lines = []
    for si, s in enumerate(plan["scenes"]):
        for li, line in enumerate(s["sentences"]):
            lines.append((s["id"], li, line))
    print(f"{len(lines)} sentences to synthesise")

    voice = load_voice()
    scale = 1.00
    attempts = []
    for _ in range(5):
        parts = run_pass(voice, lines, scale)
        gaps = [gap_after(scene) for scene, _, _ in lines]
        total = LEAD_IN_S + sum(p["seconds"] for p in parts) + sum(gaps)
        attempts.append({"length_scale": scale, "total_s": round(total, 2)})
        print(f"  length_scale {scale:.3f} -> {total:6.2f} s")
        if TARGET_MIN_S <= total <= TARGET_MAX_S:
            break
        if total < TARGET_MIN_S:
            scale = round(min(1.08, scale - 0.03), 3)
        else:
            scale = round(min(1.08, scale + 0.03), 3)
        if scale >= 1.08 and total > TARGET_MAX_S:
            print("  at the 1.08 limit and still long; accepting the measured runtime")
            break
        if scale <= 0.95 and total < TARGET_MIN_S:
            print("  at the 0.95 limit and still short; accepting the measured runtime")
            break

    parts = run_pass(voice, lines, scale)
    gaps = [gap_after(scene) for scene, _, _ in lines]

    # assemble
    lead = int(LEAD_IN_S * SR)
    total_samples = lead + sum(p["samples"] for p in parts) + int(sum(gaps) * SR)
    track = np.zeros(total_samples, dtype=np.float32)
    cursor = lead
    records = []
    for p, g in zip(parts, gaps):
        track[cursor:cursor + p["samples"]] = p["audio"]
        records.append({k: v for k, v in p.items() if k != "audio"}
                      | {"start_sample": cursor,
                         "start_seconds": round(cursor / SR, 3),
                         "gap_after_seconds": g})
        cursor += p["samples"] + int(g * SR)

    outdir = DAY / "audio"
    outdir.mkdir(exist_ok=True)
    sf.write(str(outdir / "narration_22050.wav"), track, SR, subtype="PCM_16")

    # resample to the delivery rate with a proper rational ratio (48000/22050)
    from scipy.signal import resample_poly
    from math import gcd

    g = gcd(TARGET_SR, SR)
    up, down = TARGET_SR // g, SR // g
    track48 = resample_poly(track, up, down).astype(np.float32)
    sf.write(str(outdir / "narration.wav"), track48, TARGET_SR, subtype="PCM_16")

    dur = track.size / SR
    meta = {
        "voice": voice_path().name,
        "sample_rate": SR,
        "delivery_rate": TARGET_SR,
        "length_scale": scale,
        "attempts": attempts,
        "narration_seconds": round(dur, 3),
        "narration_samples_48k": int(track48.size),
        "sentence_target_lufs": SENTENCE_LUFS,
        "gap_policy": {"default": GAP_AFTER_DEFAULT, "before_reveal": GAP_BEFORE_REVEAL,
                       "before_endcard": GAP_BEFORE_ENDCARD,
                       "lead_in_frames": LEAD_IN_FRAMES},
        "sentences": records,
    }
    (DAY / "tts_sentences.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"\nnarration {dur:.2f} s at {SR} Hz ({track48.size} samples at {TARGET_SR} Hz)")
    print(f"length_scale {scale}  sentence LUFS target {SENTENCE_LUFS}")
    print("wrote tts_sentences.json and audio/narration.wav")
    return 0


def gap_after(scene_id: str) -> float:
    if scene_id == "the_gap":       # the pause before the payoff reveal
        return GAP_BEFORE_REVEAL
    if scene_id == "question":      # the pause before the loop frame
        return GAP_BEFORE_ENDCARD
    return GAP_AFTER_DEFAULT


if __name__ == "__main__":
    sys.exit(main())