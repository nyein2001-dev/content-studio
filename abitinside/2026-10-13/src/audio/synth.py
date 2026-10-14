#!/usr/bin/env python3
"""
A Bit Inside - procedural sound (section 7.3, playbook 3.2).

Every sound here is synthesised from numpy/scipy. Nothing is sampled, downloaded
or licensed. Each generator returns mono float32 at 48 kHz.

    click / tick        2-3 kHz sine, ~6 ms exponential decay + noise transient
    tick_rise           the same, pitched upward step by step (counters)
    whoosh              band-passed noise, sweeping centre frequency, sin^2 envelope
    whoosh_rev          the same with the envelope reversed (into the loop frame)
    riser               ascending tone with swelling gain (before a reveal)
    impact              70 -> 38 Hz sine sweep, 350 ms decay + low-passed noise
    chime               two-note additive sine, 0.6 s decay
    tap                 filtered click around 1.4 kHz, very short
    typing              random-interval micro clicks, varied pitch
    buzz                110 Hz square, 150 ms (myth / unknown / wrong)
    pad                 additive chord bed, low-passed 1.8 kHz, slow breathing
    noise_floor         very low broadband air so silence never feels dead
"""
from __future__ import annotations

import math

import numpy as np
from scipy.signal import butter, lfilter, sosfilt

SR = 48000
RNG = np.random.default_rng(20261013)     # deterministic: same video every build


def _t(dur: float) -> np.ndarray:
    return np.arange(int(dur * SR), dtype=np.float64) / SR


def _env_exp(dur: float, tau: float) -> np.ndarray:
    return np.exp(-_t(dur) / tau)


def _noise(n: int) -> np.ndarray:
    return RNG.standard_normal(n)


def click(dur: float = 0.055, freq: float = 2500.0, gain: float = 0.55) -> np.ndarray:
    n = int(dur * SR)
    body = np.sin(2 * np.pi * freq * _t(dur)) * _env_exp(dur, 0.006)
    click_n = _noise(n) * np.exp(-_t(dur) / 0.0015) * 0.6
    y = body + click_n
    y = sosfilt(butter(2, 6500 / 24000, btype="lowpass", output="sos"), y)
    return (y / (np.max(np.abs(y)) + 1e-9) * gain).astype(np.float32)


def tick(freq: float = 2500.0, gain: float = 0.45) -> np.ndarray:
    return click(0.045, freq, gain)


def tick_rise(step: int = 0, gain: float = 0.32) -> np.ndarray:
    return click(0.05, 1900.0 + 260.0 * step, gain)


def tap(gain: float = 0.35) -> np.ndarray:
    return click(0.035, 1400.0, gain)


def typing(gain: float = 0.22) -> np.ndarray:
    return click(0.028, 1750.0 + RNG.integers(-320, 320), gain)


def buzz(gain: float = 0.3) -> np.ndarray:
    dur = 0.15
    t = _t(dur)
    y = np.sign(np.sin(2 * np.pi * 110 * t))
    env = np.sin(np.pi * np.linspace(0, 1, y.size)) ** 1.5
    y = y * env
    y = sosfilt(butter(2, 1800 / 24000, btype="lowpass", output="sos"), y)
    return (y / (np.max(np.abs(y)) + 1e-9) * gain).astype(np.float32)


def _swept_noise(dur: float, f_start: float, f_end: float, gain: float,
                 order: int = 4, reverse: bool = False) -> np.ndarray:
    n = int(dur * SR)
    x = _noise(n)
    # time-varying band-pass: cheap version, a chain of fixed filters swept by gain
    y = np.zeros(n)
    steps = 24
    for i in range(steps):
        a, b = int(i * n / steps), int((i + 1) * n / steps)
        if b <= a:
            continue
        k = i / max(1, steps - 1)
        fc = f_start * (f_end / f_start) ** k
        fc = max(60.0, min(fc, 9000.0))
        lo = max(1e-4, (fc * 0.55) / 24000)
        hi = min(0.999, (fc * 1.7) / 24000)
        if hi <= lo:
            hi = min(0.999, lo * 1.5)
        sos = butter(order, [lo, hi], btype="bandpass", output="sos")
        y[a:b] = sosfilt(sos, x[a:b])
    m = max(1, n - 1)
    lin = np.linspace(0, 1, n)
    env = np.sin(np.pi * lin) ** 2
    if reverse:
        env = env[::-1]
    y = y * env
    return (y / (np.max(np.abs(y)) + 1e-9) * gain).astype(np.float32)


def whoosh(gain: float = 0.5) -> np.ndarray:
    return _swept_noise(0.52, 320.0, 5200.0, gain)


def whoosh_rev(gain: float = 0.42) -> np.ndarray:
    return _swept_noise(0.6, 4200.0, 260.0, gain, reverse=True)


def riser(gain: float = 0.34) -> np.ndarray:
    dur = 2.0
    t = _t(dur)
    f = 110 + 640 * (t / dur) ** 1.6
    phase = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(phase) * 0.7 + np.sin(2 * phase) * 0.25
    y *= (np.linspace(0, 1, t.size) ** 2)
    y += _swept_noise(dur, 400, 6000, 0.28) * (np.linspace(0, 1, t.size) ** 3)
    return (y / (np.max(np.abs(y)) + 1e-9) * gain).astype(np.float32)


def impact(gain: float = 0.95) -> np.ndarray:
    dur = 0.75
    t = _t(dur)
    f = 70 - 32 * (t / dur)              # 70 Hz down to 38 Hz
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env_exp(dur, 0.16)
    burst = _noise(int(0.09 * SR)) * _env_exp(0.09, 0.022)
    burst = sosfilt(butter(3, 900 / 24000, btype="lowpass", output="sos"), burst)
    y[: burst.size] += 0.7 * burst
    y = sosfilt(butter(2, 4200 / 24000, btype="lowpass", output="sos"), y)
    return (y / (np.max(np.abs(y)) + 1e-9) * gain).astype(np.float32)


def chime(gain: float = 0.42) -> np.ndarray:
    dur = 0.9
    t = _t(dur)
    y = np.zeros(t.size)
    for f, a, start in ((880.0, 1.0, 0.0), (1318.5, 0.85, 0.0),
                        (1760.0, 0.35, 0.0)):
        y += a * np.sin(2 * np.pi * f * t + 0.4) * np.exp(-t / (0.30 + 0.1 * f / 1000))
    # soft second note, a fifth above, entering late
    n2 = int(0.14 * SR)
    y2 = np.zeros(t.size)
    tail = t[min(n2, t.size):]
    if tail.size:
        y2[min(n2, t.size):] = (np.sin(2 * np.pi * 1760.0 * tail) * np.exp(-tail / 0.55)
                                + 0.5 * np.sin(2 * np.pi * 2637.0 * tail) * np.exp(-tail / 0.4))
    y = y + y2
    return (y / (np.max(np.abs(y)) + 1e-9) * gain).astype(np.float32)


# ------------------------------------------------------------------ music bed
CHORDS = {
    "Cmaj9":   [130.81, 196.00, 246.94, 329.63, 415.30],   # C E G B D
    "Am9":     [110.00, 164.81, 220.00, 261.63, 329.63],   # A C E B E
    "Fmaj7":   [87.31, 130.81, 174.61, 220.00, 349.23],    # F A C E F
    "Cadd9":   [130.81, 196.00, 246.94, 293.66, 415.30],   # C E G D D
}


def pad(total_s: float, resolve_at: float | None = None) -> np.ndarray:
    """Additive pad, four bars, low-passed, slow breathing, very light pulse."""
    n = int(total_s * SR)
    y = np.zeros(n)
    bars = ["Cmaj9", "Am9", "Fmaj7", "Cadd9"]
    bar_len = total_s / len(bars)
    for i, name in enumerate(bars):
        chord = CHORDS[name]
        a = int(i * bar_len * SR)
        b = min(n, int((i + 1) * bar_len * SR) + int(0.9 * SR))
        seg_t = (np.arange(b - a) / SR)
        seg = np.zeros(b - a)
        for j, f in enumerate(chord):
            det = 1.0 + (0.0009 * (j - 2))
            # three partials per note keeps it additive without sounding like a sine beep
            seg += (np.sin(2 * np.pi * f * det * seg_t)
                    + 0.34 * np.sin(2 * np.pi * f * 2 * det * seg_t + 0.7)
                    + 0.13 * np.sin(2 * np.pi * f * 3 * det * seg_t + 1.3))
            seg *= 0.9 ** j
        # cross-fade the bars so the bed never restarts audibly
        fade = int(1.1 * SR)
        if i > 0:
            m = min(fade, seg.size)
            seg[:m] *= np.linspace(0, 1, m)
        if b < n:
            m = min(fade, n - b)
            seg[-m:] *= np.linspace(1, 0, m)
        y[a:b] += seg[: b - a]
    # breathing at ~0.07 Hz and a faint pulse on the bar
    tt = np.arange(n) / SR
    breath = 1.0 + 0.16 * np.sin(2 * np.pi * 0.07 * tt - 1.2)
    pulse = 1.0 + 0.05 * np.sin(2 * np.pi * 0.5 * tt) ** 2
    y *= breath * pulse
    y = sosfilt(butter(2, 1800 / 24000, btype="lowpass", output="sos"), y)
    if resolve_at is not None:
        # a soft major resolution in the last bar before the payoff
        a = int(max(0, resolve_at - 2.2) * SR)
        b = min(n, int((resolve_at + 3.0) * SR))
        if b > a:
            seg_t = np.arange(b - a) / SR
            res = np.zeros(b - a)
            for f in CHORDS["Cadd9"]:
                res += np.sin(2 * np.pi * f * seg_t) * np.exp(-seg_t / 1.6)
            res = sosfilt(butter(2, 2200 / 24000, btype="lowpass", output="sos"), res)
            env = np.minimum(1.0, np.linspace(0, 1, b - a) * 3) * np.exp(-np.clip(seg_t - 1.2, 0, 9) / 2.0)
            y[a:b] += res * env * 0.9
    return (y / (np.max(np.abs(y)) + 1e-9) * 0.32).astype(np.float32)


def noise_floor(total_s: float, gain: float = 0.0016) -> np.ndarray:
    n = int(total_s * SR)
    x = _noise(n)
    x = sosfilt(butter(2, [90 / 24000, 5200 / 24000], btype="bandpass", output="sos"), x)
    tt = np.arange(n) / SR
    return (x * (1.0 + 0.25 * np.sin(2 * np.pi * 0.05 * tt))).astype(np.float32) * gain


# ------------------------------------------------------------------ reverb
def make_ir(seconds: float = 0.55, decay: float = 5.5, pre_delay: float = 0.008) -> np.ndarray:
    n = int(seconds * SR)
    ir = _noise(n) * np.exp(-np.arange(n) / (SR * decay / 6.9))
    ir[: int(pre_delay * SR)] = 0.0
    ir[0] = 1.0
    return ir.astype(np.float32)


def db(x: float) -> float:
    return 20.0 * math.log10(max(1e-9, x))


def from_db(x: float) -> float:
    return 10 ** (x / 20.0)


def one_pole_env(x: np.ndarray, attack_s: float, release_s: float) -> np.ndarray:
    """Envelope follower with independent attack and release."""
    a = math.exp(-1.0 / max(1e-6, attack_s * SR))
    r = math.exp(-1.0 / max(1e-6, release_s * SR))
    env = np.empty_like(x)
    prev = 0.0
    for i, v in enumerate(x):
        c = a if abs(v) > prev else r
        prev = c * prev + (1 - c) * abs(v)
        env[i] = prev
    return env


def fast_env(x: np.ndarray, attack_s: float, release_s: float) -> np.ndarray:
    """Vectorised envelope follower: one-pole attack and release, take the max."""
    ax = np.abs(np.asarray(x, dtype=np.float64))
    a = math.exp(-1.0 / max(1e-6, attack_s * SR))
    r = math.exp(-1.0 / max(1e-6, release_s * SR))
    fast = lfilter([1 - a], [1, -a], ax)
    slow = lfilter([1 - r], [1, -r], ax)
    return np.maximum(fast, slow)


def limit(x: np.ndarray, ceil_db: float = -3.0, ratio: float = 20.0,
          attack_s: float = 0.001, release_s: float = 0.05) -> np.ndarray:
    """Fast peak limiter. This is what makes -14 LUFS and -1.5 dBTP reachable
    at the same time: it caps sample peaks without the pumping a hard clip gives."""
    ceil = 10 ** (ceil_db / 20.0)
    env = fast_env(x, attack_s, release_s)
    over_db = np.where(env > ceil, 20.0 * np.log10(np.maximum(env, 1e-9) / ceil), 0.0)
    gr_db = -over_db * (1.0 - 1.0 / ratio)
    return (x * (10 ** (gr_db / 20.0))).astype(np.float32)


def soft_limit(x: np.ndarray, peak_db: float = -6.0, knee: float = 0.92) -> np.ndarray:
    """Instantaneous soft-knee peak limiter (tanh).

    An envelope follower is the wrong tool here: speech peaks are only a few
    samples wide, so a one-pole envelope reads about 9 dB below the real peak and
    the limiter never engages. A static tanh knee is sample-accurate, has no
    pumping, and bounds the output by construction.
    """
    p = 10 ** (peak_db / 20.0)
    k = np.arctanh(knee)
    a = np.abs(x) / p * k
    return (np.tanh(a) / k * p * np.sign(x)).astype(np.float32)


def crest_db(x: np.ndarray) -> float:
    pk = float(np.max(np.abs(x)))
    rms = float(np.sqrt(np.mean(np.asarray(x, dtype=np.float64) ** 2)))
    return 20 * math.log10(max(1e-9, pk) / max(1e-9, rms))


def compress(x: np.ndarray, thr_db: float = -24.0, ratio: float = 3.0,
             attack_s: float = 0.005, release_s: float = 0.12) -> np.ndarray:
    """Gentle feed-forward peak compressor.

    Speech has a crest factor around 15 dB. Hitting -14 LUFS with a 15 dB crest
    would put peaks at 0 dBFS, which then forces a true-peak trim and drags the
    integrated loudness back down. Compressing to roughly 9 dB of crest is what
    lets the delivery gate satisfy BOTH "-14 LUFS" and "TP <= -1.5 dBTP".
    """
    thr = 10 ** (thr_db / 20.0)
    env = fast_env(x, attack_s, release_s)
    over_db = np.where(env > thr, 20.0 * np.log10(np.maximum(env, 1e-9) / thr), 0.0)
    gr_db = -over_db * (1.0 - 1.0 / ratio)
    return (x * (10 ** (gr_db / 20.0))).astype(np.float32)


def lowpass(x: np.ndarray, fc: float, order: int = 2) -> np.ndarray:
    return lfilter(*butter(order, fc / (SR / 2)), x).astype(np.float32)