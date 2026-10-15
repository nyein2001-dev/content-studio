#!/usr/bin/env python3
"""Shared mixer: narration + SFX + music -> a mastered 48 kHz stereo master.

Placement is by FRAME NUMBER, at 30 fps, so the picture and the sound cannot
drift. The music bed is sidechain-ducked under the narration; the master is
normalised with a two-pass FFmpeg loudnorm to the channel's target.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import numpy as np

from . import synth

SR = 48000
FPS = 30


def frame_to_sample(frame: int, fps: int = FPS, sr: int = SR) -> int:
    return int(round(frame / fps * sr))


def frames(total: int, fps: int = FPS, sr: int = SR) -> int:
    return frame_to_sample(total, fps, sr)


def fit(x: np.ndarray, n: int) -> np.ndarray:
    if len(x) >= n:
        return x[:n]
    return np.pad(x, (0, n - len(x)))


def place(buf: np.ndarray, at: int, y: np.ndarray, gain_db: float = 0.0) -> None:
    """Mix `y` into `buf` at sample `at`, adding with the requested gain."""
    if len(y) == 0:
        return
    a = max(0, at)
    b = min(len(buf), at + len(y))
    if b <= a:
        return
    buf[a:b] += y[a - at:b - at] * synth.from_db(gain_db)


def duck(envelope: np.ndarray, depth_db: float = 6.5, attack: float = 0.020,
         release: float = 0.400, sr: int = SR) -> np.ndarray:
    """Sidechain gain for the music bed: -depth_db wherever the envelope is loud."""
    from scipy.ndimage import maximum_filter1d

    n = len(envelope)
    att = max(1, int(attack * sr))
    rel = max(1, int(release * sr))
    # fast follower: fall quickly, rise slowly
    from scipy.signal import lfilter

    env = np.abs(envelope)
    peak = lfilter([1.0], [1.0, -np.exp(-1.0 / att)], env)
    peak = maximum_filter1d(peak, size=rel, mode="nearest")
    peak = np.clip(peak, 0.0, 1.0)
    g = 1.0 - peak * (1.0 - synth.from_db(-abs(depth_db)))
    return g.astype(np.float32)


def analyse(src: Path, target_i: float, target_tp: float, target_lra: float) -> dict:
    """First loudnorm pass: measure the programme."""
    ff = os.environ["FFMPEG"]
    r = subprocess.run(
        [ff, "-hide_banner", "-nostats", "-i", str(src),
         "-af", f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:print_format=json",
         "-f", "null", "-"], capture_output=True, text=True)
    err = r.stderr
    i = err.rfind("{")
    j = err.rfind("}")
    if i < 0 or j < 0:
        raise RuntimeError(f"loudnorm produced no JSON:\n{err[-800:]}")
    return json.loads(err[i:j + 1])


def apply_loudnorm(src: Path, dst: Path, measured: dict, target_i: float,
                   target_tp: float, target_lra: float) -> None:
    """Second loudnorm pass: linear normalisation plus a true-peak pass."""
    ff = os.environ["FFMPEG"]
    filt = (
        f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}"
        f":measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
        f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
        f":offset={measured.get('target_offset', 0.0)}:linear=true"
        f":print_format=summary"
    )
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
           "-af", filt, "-ar", "48000", "-ac", "2",
           "-c:a", "pcm_f32le", str(dst)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"loudnorm apply failed: {r.stderr[-800:]}")


def measure_lufs(src: Path, sr: int = SR) -> dict:
    """Measure the finished master with pyloudnorm plus a 4x true-peak estimate."""
    import soundfile as sf

    x, srate = sf.read(str(src), always_2d=True)
    mono = x.mean(axis=1)
    import pyloudnorm
    meter = pyloudnorm.Meter(srate)
    i = meter.integrated_loudness(mono.astype(np.float64))
    up = sf.read(str(src), always_2d=True)[0]
    # true peak via 4x oversampling of the loudest window
    from scipy.signal import resample_poly
    peak = 0.0
    step = sr * 2
    for k in range(0, len(mono), step):
        seg = mono[k:k + step]
        if len(seg) < 64:
            continue
        up4 = resample_poly(seg, 4, 1)
        peak = max(peak, float(np.abs(up4).max()))
    tp = synth.db(peak) if peak > 0 else -120.0
    return {"integrated_lufs": float(i), "true_peak_dbtp": float(tp),
            "sample_peak_dbfs": synth.db(float(np.abs(mono).max()) or 1e-9),
            "duration_s": len(mono) / srate}


def silence_gaps(x: np.ndarray, floor_db: float = -62.0, window_s: float = 0.05,
                 sr: int = SR) -> list[tuple[float, float]]:
    """Interior runs quieter than `floor_db`, as (start_s, end_s)."""
    w = max(1, int(window_s * sr))
    n = len(x) // w
    if n < 2:
        return []
    fr = x[:n * w].astype(np.float64).reshape(n, w)
    rms = np.sqrt((fr ** 2).mean(axis=1)) + 1e-12
    quiet = 20 * np.log10(rms) < floor_db
    runs, start = [], None
    for i, q in enumerate(quiet):
        if q and start is None:
            start = i
        elif not q and start is not None:
            runs.append((start * window_s, i * window_s))
            start = None
    if start is not None:
        runs.append((start * window_s, n * window_s))
    return runs


def write_wav(path: Path, x: np.ndarray, sr: int = SR) -> None:
    import soundfile as sf

    path.parent.mkdir(parents=True, exist_ok=True)
    a = np.asarray(x, dtype=np.float32)
    if a.ndim == 1:
        a = np.stack([a, a], axis=1)
    sf.write(str(path), a, sr, subtype="PCM_16")


def write_cue_sheet(path: Path, events: list[dict], total_frames: int) -> None:
    """Every sound event: frame, time, type, gain."""
    lines = [
        "ARKAD'S LEDGER - CUE SHEET",
        "=" * 78,
        f"frames: {len(events)}    duration: {total_frames / FPS:.3f}s"
        f"    rate: {FPS} fps / {SR} Hz",
        "",
        f"{'frame':>7}  {'time':>9}  {'gain':>7}  {'kind':<18} detail",
        "-" * 78,
    ]
    for e in sorted(events, key=lambda d: d["frame"]):
        t = e["frame"] / FPS
        lines.append(f"{e['frame']:>7}  {int(t // 60):02d}:{t % 60:06.3f}  "
                     f"{e.get('gain_db', 0.0):>7.1f}  {e['kind']:<18} {e.get('detail', '')}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")