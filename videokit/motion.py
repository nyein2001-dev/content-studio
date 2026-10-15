#!/usr/bin/env python3
"""Shared motion vocabulary: easings and frame math.

Channel-independent. Every channel uses the same easing set so a pop on one
channel reads at the same rate as a pop on another.
"""
from __future__ import annotations

import math


def clamp01(t: float) -> float:
    return 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else (hi if v > hi else v)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def progress(frame: float, start: float, end: float) -> float:
    """Normalised 0..1 position of `frame` inside [start, end)."""
    if end <= start:
        return 1.0 if frame >= end else 0.0
    return clamp01((frame - start) / (end - start))


def ease_out_cubic(t: float) -> float:
    t = clamp01(t)
    return 1.0 - (1.0 - t) ** 3


def ease_in_cubic(t: float) -> float:
    t = clamp01(t)
    return t ** 3


def ease_in_out_cubic(t: float) -> float:
    t = clamp01(t)
    return 4 * t ** 3 if t < 0.5 else 1 - ((-2 * t + 2) ** 3) / 2


def ease_out_quad(t: float) -> float:
    t = clamp01(t)
    return 1 - (1 - t) ** 2


def ease_in_out_sine(t: float) -> float:
    return -(math.cos(math.pi * clamp01(t)) - 1) / 2


def ease_out_back(t: float, overshoot: float = 1.70158) -> float:
    """Pops only. Never use on a data-driven draw."""
    t = clamp01(t) - 1.0
    return 1 + (overshoot + 1) * t ** 3 + overshoot * t ** 2


def ease_out_elastic(t: float, amp: float = 1.0, period: float = 0.36) -> float:
    t = clamp01(t)
    if t in (0.0, 1.0):
        return t
    s = period / 4
    return amp * (2 ** (-10 * t)) * math.sin((t - s) * (2 * math.pi) / period) + 1


def pulse(frame: float, start: float, end: float, hz: float = 1.6,
          lo: float = 0.82, hi: float = 1.12) -> float:
    """A slow breathing scale between lo and hi, active inside [start, end)."""
    t = progress(frame, start, end)
    if t <= 0.0 or t >= 1.0:
        return 1.0
    return lo + (hi - lo) * (0.5 + 0.5 * math.sin(2 * math.pi * hz * (frame - start) / 30.0))


def shake(frame: float, start: float, end: float, amp: float = 7.0,
          hz: float = 17.0) -> tuple[float, float]:
    """Sub-pixel-looking shake envelope, hard capped so it never leaves the safe area."""
    t = progress(frame, start, end)
    if t <= 0.0 or t >= 1.0:
        return 0.0, 0.0
    env = math.sin(math.pi * t) ** 0.7
    a = amp * env
    ph = 2 * math.pi * hz * (frame - start) / 30.0
    return a * math.sin(ph), a * math.sin(ph * 1.37 + 1.1)


def frames(seconds: float, fps: int = 30) -> int:
    return int(round(seconds * fps))