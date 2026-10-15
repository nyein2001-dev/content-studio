#!/usr/bin/env python3
"""Build the master: narration + SFX + music, normalised to -16 LUFS.

Placement comes from timeline.json, which names every sound by frame. The SFX
bus gets a short convolution reverb, the music bed is sidechain-ducked under
the narration, and everything fades out under the end card.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3]))

import numpy as np  # noqa: E402

import theme as T  # noqa: E402
from videokit.audio import mix as M  # noqa: E402
from videokit.audio import synth as S  # noqa: E402

DAY = HERE.parent
AUDIO = DAY / "audio"
TL = json.loads((DAY / "timeline.json").read_text(encoding="utf-8"))
FPS = T.FPS
SR = S.SR


def make_sfx(kind: str, detail: str, gain_db: float, index: int) -> np.ndarray:
    """The money palette. Pitch rises with value, falls with loss."""
    step = index
    if kind == "coin_clink":
        return S.coin_clink(2100.0, 0.32, 0.42)
    if kind == "ledger_tick":
        return S.ledger_tick(min(step, 12), 0.30)
    if kind == "riser":
        return S.riser(1.9, 0.32)
    if kind == "impact":
        return S.impact(1.05, 0.95)
    if kind == "shock_ring":
        return S.coin_clink(1180.0, 0.9, 0.30)
    if kind == "whoosh":
        return S.whoosh(0.32, 0.40, seed=index + 5)
    if kind == "chime":
        return S.chime((783.99, 1174.66), 1.30, 0.40)
    if kind == "map_swell":
        return S.map_swell(1.4, 0.34)
    if kind == "pin_drop":
        return S.pin_drop(0.40)
    if kind == "route_swish":
        return S.route_swish(0.85, 0.30)
    if kind == "route_coin":
        return S.route_coin(0.18, 0.16)
    if kind == "receipt_print":
        return S.receipt_print(0.55, 0.26)
    if kind == "low_buzz":
        return S.low_buzz(0.55, 0.30)
    raise KeyError(f"unknown sound kind {kind!r}")


def _true_peak(y: np.ndarray) -> float:
    """True peak in dBTP, estimated by 4x oversampling."""
    from scipy.signal import resample_poly

    worst = 0.0
    step = SR * 2
    for i in range(0, len(y), step):
        seg = y[i:i + step]
        if len(seg) < 64:
            continue
        worst = max(worst, float(np.abs(resample_poly(seg, 4, 1)).max()))
    return S.db(worst) if worst > 0 else -120.0


def main() -> int:
    AUDIO.mkdir(parents=True, exist_ok=True)
    total = TL["total_frames"]
    n = M.frames(total)
    dur = total / FPS
    print(f"master: {total} frames = {dur:.2f}s")

    # ---------------------------------------------------------------- narration
    import soundfile as sf

    narr, sr = sf.read(str(AUDIO / "narration.wav"), always_2d=True)
    narr = narr.mean(axis=1).astype(np.float32)
    narr = M.fit(narr, n)
    # phone-speaker clarity
    narr = S.highpass(narr, 80.0)
    narr = S.lowpass(narr, 16000.0)
    M.write_wav(AUDIO / "narration_stem.wav", narr, SR)

    # ---------------------------------------------------------------------- sfx
    sfx = np.zeros(n, dtype=np.float32)
    ir = S.make_ir(0.45, 5.0, 0.006, SR)
    wet = np.zeros(n, dtype=np.float32)
    counts: dict[str, int] = {}
    for e in TL["audio"]:
        idx = counts.get(e["kind"], 0)
        counts[e["kind"]] = idx + 1
        try:
            y = make_sfx(e["kind"], e.get("detail", ""), e.get("gain_db", 0.0), idx)
        except KeyError as exc:
            print(f"  skipping unknown kind: {exc}")
            continue
        at = M.frame_to_sample(e["frame"])
        M.place(sfx, at, y, e.get("gain_db", 0.0))
        M.place(wet, at, S.convolve(y, ir)[:len(y)], e.get("gain_db", 0.0) - 4.0)
    sfx_bus = sfx + wet * 0.35
    # keep transients from dominating the crest factor so the master can
    # actually reach -16 LUFS without the limiter clamping everything
    sfx_bus = S.soft_limit(sfx_bus, -9.0)
    sfx_bus = sfx_bus * S.from_db(-3.0)
    M.write_wav(AUDIO / "sfx.wav", sfx_bus, SR)
    print(f"  sfx: {len(TL['audio'])} events, {len(counts)} kinds, "
          f"peak {S.db(float(np.abs(sfx_bus).max())):.1f} dBFS")

    # -------------------------------------------------------------------- music
    payoff_frame = next((s["end"] for s in TL["scenes"] if s["id"] == "payoff"),
                        int(total * 0.75))
    music = S.music_bed(dur, bar_s=7.2, resolve_at=payoff_frame / FPS, sr=SR)
    music = music + S.noise_floor(dur, 0.0016, SR)
    duck_gain = M.duck(narr, T.DUCK_DEPTH_DB, T.DUCK_ATTACK, T.DUCK_RELEASE, SR)
    music = M.fit(music, n) * duck_gain
    music = music * S.from_db(T.MUSIC_UNDER_NARRATION_DB)
    # fade out under the end card
    ec = M.frame_to_sample(TL["endcard"]["start"])
    fade = np.ones(n, dtype=np.float32)
    f0 = max(0, ec - int(1.6 * SR))
    ramp = np.linspace(1.0, 0.0, max(1, n - f0), dtype=np.float32)
    fade[f0:] = ramp
    music = music * fade
    M.write_wav(AUDIO / "music.wav", music, SR)

    # -------------------------------------------------------------------- mix
    master = narr + sfx_bus + music
    master = S.compress(master, -24.0, 4.0, 0.003, 0.180, 5.0)
    master = S.soft_limit(master, -3.0)
    peak = float(np.abs(master).max())
    if peak > 0.99:
        master *= 0.99 / peak
    pre = S.db(peak) if peak > 0 else -120.0
    print(f"  pre-master peak {pre:.2f} dBFS")
    M.write_wav(AUDIO / "master_ungained.wav", master, SR)

    # ------------------------------------------------------- two-pass loudnorm
    # Pass 1 measures with FFmpeg loudnorm. Pass 2 is an explicit gain plus a
    # true-peak limiter, then re-measure and iterate: FFmpeg's own linear mode
    # can land several dB under target when the source already sits near the
    # true-peak ceiling, which it does here.
    measured = M.analyse(AUDIO / "master_ungained.wav", T.TARGET_I, T.TARGET_TP,
                         T.TARGET_LRA)
    print(f"  pass 1: I={measured['input_i']} TP={measured['input_tp']} "
          f"LRA={measured['input_lra']}")

    gain_db = T.TARGET_I - float(measured["input_i"])
    applied = 0.0
    got = None
    # A 13 dB crest factor cannot hold -16 LUFS and -1.5 dBTP at the same time by
    # gain alone, so the peaks are limited and then a final static safety trim
    # lands the TRUE peak exactly on target. Measured, not guessed.
    ceiling_db = -7.0
    extra_db = 0.0
    gain_db = T.TARGET_I - float(measured["input_i"])
    applied = 0.0
    got = None
    best = None          # the best candidate that satisfies BOTH gates
    for attempt in range(12):
        y = S.limit(master * S.from_db(gain_db), ceiling_db, 0.0015, 0.120,
                    0.006, SR) * S.from_db(extra_db)
        M.write_wav(AUDIO / "master_ungained.wav", y, SR)
        got = M.measure_lufs(AUDIO / "master_ungained.wav")
        tp = got["true_peak_dbtp"]
        drift = T.TARGET_I - got["integrated_lufs"]
        print(f"  pass {attempt + 2}: gain {gain_db:+.2f} trim {extra_db:+.2f} -> "
              f"I={got['integrated_lufs']:.2f} LUFS TP={tp:.2f} dBTP "
              f"crest {got['sample_peak_dbfs'] - got['integrated_lufs']:.1f} dB")
        applied = gain_db + extra_db
        if (abs(drift) <= 0.5 and tp <= T.TARGET_TP
                and (best is None or abs(drift) < abs(best[1]))):
            best = (y.copy(), drift, got)
            print("       ^ compliant candidate kept")
        if tp > T.TARGET_TP:
            extra_db -= (tp - T.TARGET_TP) + 0.10          # land the true peak
            continue
        if abs(drift) <= 0.15:
            break
        measured = M.analyse(AUDIO / "master_ungained.wav", T.TARGET_I,
                             T.TARGET_TP, T.TARGET_LRA)
        gain_db += drift

    if best is not None:
        y = best[0]
        got = best[2]
        print(f"  using the compliant candidate (drift {best[1]:+.2f} LUFS)")
    M.write_wav(AUDIO / "master_final.wav", y, SR)
    got = M.measure_lufs(AUDIO / "master_final.wav")
    print(f"  master: I={got['integrated_lufs']:.2f} LUFS  "
          f"TP={got['true_peak_dbtp']:.2f} dBTP  dur={got['duration_s']:.2f}s")

    # a no-narration cut is useful for the caption check
    M.write_wav(AUDIO / "master_music_sfx_only.wav", sfx_bus + music, SR)

    M.write_cue_sheet(DAY / "cue-sheet.txt", TL["audio"], total)
    (AUDIO / "loudness.json").write_text(json.dumps(
        {"target": {"I": T.TARGET_I, "TP": T.TARGET_TP, "LRA": T.TARGET_LRA},
         "measured_pass1": measured, "measured_final": got,
         "applied_gain_db": round(applied, 3),
         "pre_master_peak_dbfs": pre}, indent=2), encoding="utf-8")
    print(f"  -> {AUDIO / 'master_final.wav'}")
    print(f"  -> {DAY / 'cue-sheet.txt'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
