#!/usr/bin/env python3
"""Shared procedural audio: SFX generators and a music bed.

Everything is synthesised from scratch with numpy/scipy. No sample libraries, no
stock music, nothing downloaded. Each generator returns a float32 mono buffer at
48 kHz so the mixer can place it on an exact frame.
"""
from __future__ import annotations

import numpy as np

SR = 48000


# ------------------------------------------------------------------ helpers
def db(x: float) -> float:
    return float(20.0 * np.log10(max(1e-9, x)))


def from_db(x: float) -> float:
    return float(10.0 ** (x / 20.0))


def n_samples(seconds: float, sr: int = SR) -> int:
    return max(1, int(round(seconds * sr)))


def env(n: int, attack: float = 0.004, decay: float = 0.08, sustain: float = 0.0,
        release: float = 0.06, sr: int = SR) -> np.ndarray:
    a, d, r = n_samples(attack, sr), n_samples(decay, sr), n_samples(release, sr)
    s = max(0, n - a - d - r)
    parts = [np.linspace(0, 1, a, endpoint=False) if a else np.zeros(0),
             np.linspace(1, sustain, d, endpoint=False) if d else np.zeros(0),
             np.full(s, sustain),
             np.linspace(sustain, 0, r) if r else np.zeros(0)]
    e = np.concatenate(parts)
    return e[:n] if len(e) >= n else np.pad(e, (0, n - len(e)))


def tone(freq: float, seconds: float, amp: float = 1.0, harm: float = 0.0,
         sr: int = SR) -> np.ndarray:
    t = np.arange(n_samples(seconds, sr)) / sr
    x = np.sin(2 * np.pi * freq * t)
    if harm:
        x += harm * np.sin(4 * np.pi * freq * t)
    return (amp * x).astype(np.float32)


def noise(seconds: float, sr: int = SR, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.standard_normal(n_samples(seconds, sr)).astype(np.float32)


def swept_noise(f0: float, f1: float, seconds: float, seed: int = 0,
                sr: int = SR) -> np.ndarray:
    n = n_samples(seconds, sr)
    rng = np.random.default_rng(seed)
    from scipy.signal import lfilter

    x = rng.standard_normal(n).astype(np.float32)
    f = np.linspace(f0, f1, n)
    y = np.empty(n, dtype=np.float32)
    # one-pole lowpass with a time-varying cutoff
    for i in range(n):
        a = float(np.clip(f[i] / (sr / 2.0), 1e-4, 0.99))
        x[i] *= a
        y[i] = x[i]
    return y.astype(np.float32)


def lowpass(x: np.ndarray, fc: float, order: int = 2, sr: int = SR) -> np.ndarray:
    from scipy.signal import butter, sosfilt

    if fc >= sr / 2.0 * 0.97:
        return x
    sos = butter(order, fc / (sr / 2.0), btype="low", output="sos")
    return sosfilt(sos, x).astype(np.float32)


def highpass(x: np.ndarray, fc: float, order: int = 2, sr: int = SR) -> np.ndarray:
    from scipy.signal import butter, sosfilt

    sos = butter(order, fc / (sr / 2.0), btype="high", output="sos")
    return sosfilt(sos, x).astype(np.float32)


def compress(x: np.ndarray, thr_db: float = -26.0, ratio: float = 3.0,
             attack_s: float = 0.004, release_s: float = 0.140,
             makeup_db: float = 0.0, sr: int = SR) -> np.ndarray:
    """Gentle feed-forward compressor.

    A narration-plus-music mix has a crest factor around 13 dB, and at that
    crest -16 LUFS and -1.5 dBTP cannot both be reached by gain alone. Pulling
    the peaks toward the body is what makes both targets reachable at once.
    """
    thr = from_db(thr_db)
    env = np.abs(x.astype(np.float64))
    a = float(np.exp(-1.0 / max(1e-6, attack_s * sr)))
    r = float(np.exp(-1.0 / max(1e-6, release_s * sr)))
    follow = np.empty_like(env)
    prev = 0.0
    for i in range(env.size):
        e = env[i]
        prev = a * e + (1 - a) * prev if e > prev else r * e + (1 - r) * prev
        follow[i] = prev
    over = follow > thr
    gain = np.ones_like(follow)
    gain[over] = (thr * (follow[over] / thr) ** (1.0 / ratio)) / follow[over]
    k = max(1, int(0.002 * sr))
    gain = np.convolve(gain, np.ones(k) / k, mode="same")
    return (x * gain.astype(np.float32) * from_db(makeup_db)).astype(np.float32)


def limit(x: np.ndarray, ceiling_db: float = -1.5, attack_s: float = 0.0015,
          release_s: float = 0.060, lookahead_s: float = 0.004, sr: int = SR) -> np.ndarray:
    """A real peak limiter: attenuate the peaks, leave the rest of the programme.

    An envelope follower with a fast attack and a slow release finds the gain
    reduction each sample needs, so raising the master gain raises the loudness
    instead of being clamped back by a whole-file attenuation.
    """
    ceiling = from_db(ceiling_db)
    n = len(x)
    if n == 0:
        return x
    a = float(np.exp(-1.0 / max(1e-6, attack_s * sr)))
    r = float(np.exp(-1.0 / max(1e-6, release_s * sr)))
    env = np.abs(x).astype(np.float64)
    # look-ahead: the detector sees a few ms early so the gain is already down
    la = max(0, int(lookahead_s * sr))
    if la:
        env = np.maximum(env, np.concatenate([env[la:], np.full(la, env[-1])]))
    follow = np.empty(n, dtype=np.float64)
    prev = 0.0
    for i in range(n):
        e = env[i]
        prev = a * e + (1 - a) * prev if e > prev else r * e + (1 - r) * prev
        follow[i] = prev
    gain = np.ones(n, dtype=np.float64)
    over = follow > ceiling
    gain[over] = ceiling / follow[over]
    # smooth the gain so it does not chatter
    k = max(1, int(0.0015 * sr))
    gain = np.convolve(gain, np.ones(k) / k, mode="same")
    return (x * gain.astype(np.float32)).astype(np.float32)


def soft_limit(x: np.ndarray, ceiling_db: float = -1.0) -> np.ndarray:
    ceiling = from_db(ceiling_db)
    a = np.abs(x)
    over = a > ceiling
    y = x.copy()
    y[over] = np.sign(x[over]) * (ceiling + np.tanh((a[over] - ceiling) / ceiling) * ceiling * 0.25)
    return y.astype(np.float32)


def make_ir(seconds: float = 0.55, decay: float = 5.5, pre_delay: float = 0.008,
            sr: int = SR, seed: int = 7) -> np.ndarray:
    """A short synthetic room for the SFX bus."""
    n = n_samples(seconds, sr)
    ir = np.zeros(n, dtype=np.float32)
    pd = n_samples(pre_delay, sr)
    rng = np.random.default_rng(seed)
    body = rng.standard_normal(n - pd).astype(np.float32)
    body *= np.exp(-decay * np.arange(body.size) / sr).astype(np.float32)
    ir[pd:] = body
    ir /= np.abs(ir).max() + 1e-9
    return ir


def convolve(x: np.ndarray, ir: np.ndarray) -> np.ndarray:
    from scipy.signal import fftconvolve

    return fftconvolve(x, ir, mode="full")[:len(x)].astype(np.float32)


# ------------------------------------------------------------------ money SFX
def coin_clink(freq: float = 2100.0, seconds: float = 0.32, amp: float = 0.42,
               seed: int = 3) -> np.ndarray:
    """Soft coin clink: inharmonic bell partials with a fast decay."""
    n = n_samples(seconds)
    t = np.arange(n) / SR
    ratios = (1.0, 2.76, 5.40, 8.93)          # deliberately inharmonic
    gains = (1.0, 0.55, 0.30, 0.14)
    x = np.zeros(n, dtype=np.float32)
    for k, (r, g) in enumerate(zip(ratios, gains)):
        d = np.exp(-(6.5 + k * 2.4) * t)
        x += (g * d * np.sin(2 * np.pi * freq * r * t + k)).astype(np.float32)
    x *= env(n, 0.0015, 0.02, 0.0, 0.20)
    rng = np.random.default_rng(seed)
    k = n_samples(0.006, SR)
    x[:k] += 0.30 * rng.standard_normal(k).astype(np.float32)
    return (amp * x / (np.abs(x).max() + 1e-9)).astype(np.float32)


def ledger_tick(step: int = 0, amp: float = 0.30, base: float = 2100.0) -> np.ndarray:
    """Counter tick; pitch climbs with the value so growth is audible."""
    freq = base * (2 ** (step / 12.0))
    n = n_samples(0.085)
    t = np.arange(n) / SR
    body = np.exp(-42 * t) * (np.sin(2 * np.pi * freq * t) + 0.4 * np.sin(4 * np.pi * freq * t))
    k = n_samples(0.003, SR)
    tick = np.exp(-260 * t[:k]) * noise(0.003, seed=int(step) + 1)
    tick = np.pad(tick, (0, max(0, n - len(tick))))[:n]
    x = body + 0.5 * tick
    return (amp * x / (np.abs(x).max() + 1e-9)).astype(np.float32)


def receipt_print(seconds: float = 0.55, amp: float = 0.26) -> np.ndarray:
    """Soft paper/receipt chatter for the Receipt format."""
    rng = np.random.default_rng(11)
    n = n_samples(seconds)
    x = np.zeros(n, dtype=np.float32)
    pos, gap = 0, n_samples(0.032)
    while pos < n - gap:
        burst = rng.standard_normal(gap).astype(np.float32)
        burst *= np.exp(-np.linspace(0, 6, gap)).astype(np.float32)
        x[pos:pos + gap] += burst
        pos += gap + int(gap * rng.uniform(0.45, 0.95))
    x = highpass(x, 1400.0)
    x = lowpass(x, 8200.0)
    return (amp * x / (np.abs(x).max() + 1e-9)).astype(np.float32)


def whoosh(seconds: float = 0.32, amp: float = 0.42, seed: int = 5) -> np.ndarray:
    """Cut whoosh: band-passed noise sweeping up."""
    n = n_samples(seconds)
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n).astype(np.float32)
    from scipy.signal import butter, sosfilt

    t = np.linspace(0, 1, n)
    y = np.empty(n, dtype=np.float32)
    prev = 0.0
    for i in range(n):
        fc = 340.0 * (5200.0 / 340.0) ** t[i]
        a = float(np.clip(fc / (SR / 2.0), 1e-4, 0.98))
        prev = prev + a * (x[i] - prev)
        y[i] = prev
    y *= np.sin(np.pi * np.clip(t, 0, 1)).astype(np.float32)
    return (amp * y / (np.abs(y).max() + 1e-9)).astype(np.float32)


def impact(seconds: float = 1.05, amp: float = 0.95) -> np.ndarray:
    """Sub-drop plus a thump, for the key reveal."""
    n = n_samples(seconds)
    t = np.arange(n) / SR
    f = 82.0 * np.exp(-t * 7.0) + 34.0
    phase = 2 * np.pi * np.cumsum(f) / SR
    sub = np.sin(phase) * np.exp(-t * 5.2)
    k = n_samples(0.02, SR)
    click = noise(0.02, seed=17) * np.exp(-np.arange(k) / SR * 420)
    click = np.pad(click, (0, max(0, n - len(click))))
    x = sub + 0.55 * click[:n]
    return (amp * x / (np.abs(x).max() + 1e-9)).astype(np.float32)


def low_buzz(seconds: float = 0.55, amp: float = 0.30, freq: float = 108.0) -> np.ndarray:
    """Low buzz for myth / loss beats."""
    n = n_samples(seconds)
    t = np.arange(n) / SR
    sq = np.sign(np.sin(2 * np.pi * freq * t))
    x = sq * 0.6 + 0.4 * np.sin(4 * np.pi * freq * t)
    x *= env(n, 0.012, 0.10, 0.55, 0.22)
    return (amp * x / (np.abs(x).max() + 1e-9)).astype(np.float32)


def riser(seconds: float = 1.9, amp: float = 0.32, seed: int = 23) -> np.ndarray:
    """Tension riser into the biggest reveal."""
    n = n_samples(seconds)
    t = np.linspace(0, 1, n)
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n).astype(np.float32)
    from scipy.signal import butter, sosfilt

    prev = 0.0
    for i in range(n):
        fc = 140.0 * (5.2 ** t[i])
        a = float(np.clip(fc / (SR / 2.0), 1e-4, 0.985))
        prev = prev + a * (x[i] - prev)
        x[i] = prev
    tone_a = np.sin(2 * np.pi * (120 + 420 * t) * (np.arange(n) / SR)).astype(np.float32)
    x = 0.72 * x + 0.45 * tone_a
    x *= (t ** 1.6).astype(np.float32)
    return (amp * x / (np.abs(x).max() + 1e-9)).astype(np.float32)


def chime(freqs=(880.0, 1174.7), seconds: float = 1.30, amp: float = 0.40) -> np.ndarray:
    """Warm two-note chime for the payoff / end card (the sonic logo)."""
    n = n_samples(seconds)
    t = np.arange(n) / SR
    x = np.zeros(n, dtype=np.float32)
    for k, f in enumerate(freqs):
        off = int(k * 0.17 * SR)
        d = np.exp(-2.9 * t)
        seg = (d * (np.sin(2 * np.pi * f * t) + 0.30 * np.sin(4 * np.pi * f * t)
                    + 0.12 * np.sin(6 * np.pi * f * t))).astype(np.float32)
        end = min(n, off + len(seg))
        x[off:end] += seg[:end - off]
    return (amp * x / (np.abs(x).max() + 1e-9)).astype(np.float32)


# ------------------------------------------------------------------ map cues
def map_swell(seconds: float = 1.4, amp: float = 0.34) -> np.ndarray:
    """Low swell under every camera zoom."""
    n = n_samples(seconds)
    t = np.arange(n) / SR
    f = 62.0 + 34.0 * (t / max(t[-1], 1e-6))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR).astype(np.float32)
    x += 0.30 * np.sin(2 * np.pi * f * 1.5).astype(np.float32)
    x *= np.sin(np.pi * np.clip(t / max(t[-1], 1e-6), 0, 1)).astype(np.float32)
    return (amp * x / (np.abs(x).max() + 1e-9)).astype(np.float32)


def pin_drop(amp: float = 0.40) -> np.ndarray:
    """Marker pin landing."""
    n = n_samples(0.26)
    t = np.arange(n) / SR
    f = 1750.0 * np.exp(-t * 11.0) + 420.0
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9.0)
    tick_n = n_samples(0.004, SR)
    x[:tick_n] += 0.35 * noise(0.004, seed=31) * np.exp(-np.arange(tick_n) / SR * 300)
    return (amp * x / (np.abs(x).max() + 1e-9)).astype(np.float32)


def route_swish(seconds: float = 0.85, amp: float = 0.30, seed: int = 41) -> np.ndarray:
    """Progressive route draw."""
    n = n_samples(seconds)
    t = np.linspace(0, 1, n)
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n).astype(np.float32)
    from scipy.signal import butter, sosfilt

    prev = 0.0
    for i in range(n):
        fc = 500.0 * (3.4 ** t[i])
        a = float(np.clip(fc / (SR / 2.0), 1e-4, 0.985))
        prev = prev + a * (x[i] - prev)
        x[i] = prev
    x = highpass(x, 380.0)
    x *= np.sin(np.pi * t).astype(np.float32)
    return (amp * x / (np.abs(x).max() + 1e-9)).astype(np.float32)


def route_coin(seconds: float = 0.18, amp: float = 0.16) -> np.ndarray:
    """Coin tick riding a route as money moves along it."""
    return (coin_clink(1650.0, seconds, amp) * 0.9).astype(np.float32)


# ------------------------------------------------------------------ music bed
CHORDS = {
    # (root Hz, intervals as semitone offsets) - Dm9 -> Bbmaj7 -> Fmaj7 -> Cadd9
    "Dm9": (146.83, (0, 3, 7, 10, 14)),
    "Bbmaj7": (116.54, (0, 4, 7, 11, 14)),
    "Fmaj7": (174.61, (0, 4, 7, 11, 14)),
    "Cadd9": (130.81, (0, 4, 7, 10, 14)),
}


def pad(chord: str, seconds: float, amp: float = 0.22, sr: int = SR) -> np.ndarray:
    root, intervals = CHORDS[chord]
    n = n_samples(seconds, sr)
    t = np.arange(n) / sr
    x = np.zeros(n, dtype=np.float32)
    for k, iv in enumerate(intervals):
        f = root * (2 ** (iv / 12.0))
        det = 1.0 + 0.0016 * k
        x += ((0.9 if k == 0 else 0.62) * np.sin(2 * np.pi * f * det * t)).astype(np.float32)
    # slow breathing
    x *= (0.72 + 0.28 * np.sin(2 * np.pi * 0.11 * t - 1.2)).astype(np.float32)
    x *= env(n, seconds * 0.22, seconds * 0.18, 0.82, seconds * 0.30, sr)
    return (amp * x / (np.abs(x).max() + 1e-9)).astype(np.float32)


def music_bed(total_s: float, bar_s: float = 7.2, resolve_at: float | None = None,
              sr: int = SR) -> np.ndarray:
    """Dm9 -> Bbmaj7 -> Fmaj7 -> Cadd9, low-passed and very slightly darker than
    the reference channel. Resolves to a major chord at `resolve_at`."""
    prog = ("Dm9", "Bbmaj7", "Fmaj7", "Cadd9")
    n = n_samples(total_s, sr)
    bed = np.zeros(n, dtype=np.float32)
    i = 0
    while i * bar_s < total_s:
        chord = prog[i % len(prog)]
        seg = pad(chord, bar_s * 1.06, 0.20, sr)
        a = int(round(i * bar_s))
        b = int(min(n, a + len(seg)))
        bed[a:b] += seg[: b - a]
        i += 1
    bed = lowpass(bed, 1800.0, 2, sr)

    if resolve_at is not None:
        k = int(resolve_at * sr)
        if 0 < k < n:
            tail = pad("Cadd9", max(1.0, float(total_s) - float(resolve_at) + 1.0), 0.26, sr)
            m = int(min(int(n) - k, len(tail)))
            if m > 0:
                fade = np.linspace(0.0, 1.0, m).astype(np.float32)
                bed[k:k + m] = bed[k:k + m] * (1 - fade) + tail[:m] * fade
    return bed.astype(np.float32)


def noise_floor(total_s: float, amp: float = 0.0016, sr: int = SR) -> np.ndarray:
    """A very low floor so silence never feels dead."""
    rng = np.random.default_rng(99)
    x = rng.standard_normal(n_samples(total_s, sr)).astype(np.float32)
    x = lowpass(x, 380.0, 2, sr)
    x = highpass(x, 28.0, 2, sr)
    return (amp * x).astype(np.float32)