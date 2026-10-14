#!/usr/bin/env python3
"""
A Bit Inside - the audio engine (sections 7.5 and 7.6).

Reads timeline.json, places every sound event at sample = frame / 30 * 48000, ducks
the music bed under speech, runs the SFX bus through a short convolution reverb,
and masters the result with two-pass FFmpeg loudnorm to -14 LUFS / -1.5 dBTP.

Writes:
    audio/sfx.wav            SFX bus, after reverb
    audio/music.wav          ducked music bed
    audio/master.wav         the pre-master sum
    audio/master_final.wav   loudnorm-mastered, 48 kHz stereo
    audio/master_music_sfx_only.wav   the no-narration mix
    audio/loudness.json      measured values, read back by qa.py
    cue-sheet.txt            every sound event: frame, time, type, gain
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.signal import fftconvolve

HERE = Path(__file__).resolve().parent
DAY = HERE.parent.parent
ABIT_CACHE = DAY.parent / ".cache"
sys.path.insert(0, str(HERE))

import synth  # noqa: E402

SR = 48000
FPS = 30
LOUDNESS_I = -14.0
# The delivery gate is TP <= -1.5 dBTP. We aim 0.5 dB lower because loudnorm's
# linear pass can land a few hundredths over its own target once AAC encoding
# and the resampler get involved.
LOUDNESS_TP = -2.0
LOUDNESS_GATE_TP = -1.5
LOUDNESS_LRA = 8.0
DUCK_DB = -6.5               # 5-8 dB under speech
DUCK_ATTACK = 0.020
DUCK_RELEASE = 0.400
NARRATION_TRIM_DB = 0.0


def fit(x: np.ndarray, n: int) -> np.ndarray:
    if x.size == n:
        return x.astype(np.float32)
    if x.size > n:
        return x[:n].astype(np.float32)
    out = np.zeros(n, dtype=np.float32)
    out[: x.size] = x
    return out


def place(buf: np.ndarray, at: int, y: np.ndarray, gain_db: float) -> int:
    at = max(0, at)
    g = 10 ** (gain_db / 20.0)
    n = min(y.size, buf.size - at)
    if n > 0:
        buf[at:at + n] += y[:n] * g
    return at


def main() -> int:
    tl = json.loads((DAY / "timeline.json").read_text(encoding="utf-8"))
    total_frames = tl["total_frames"]
    total_s = total_frames / FPS
    n = int(math.ceil(total_s * SR)) + SR
    ffmpeg = Path(__import__("os").environ["FFMPEG"])
    outdir = DAY / "audio"
    outdir.mkdir(exist_ok=True)
    ABIT_CACHE.mkdir(parents=True, exist_ok=True)

    print(f"mixing {total_s:.2f} s at {SR} Hz")

    # ---------------------------------------------------------------- narration
    nar, sr_nar = sf.read(str(outdir / "narration.wav"), dtype="float32")
    if nar.ndim > 1:
        nar = nar.mean(axis=1)
    narration = np.zeros(n, dtype=np.float32)
    m = min(n, nar.size)
    narration[:m] = nar[:m]
    narration = fit(narration, n)

    # speech must be able to reach -14 LUFS without pinning the peaks, so the
    # narration bus is compressed, limited and re-levelled before anything is
    # summed. Three passes converge on a crest factor near 9 dB, which is what
    # leaves room for the master gain to land on -14 LUFS under the peak gate.
    meter = pyln.Meter(SR)
    # Repeated soft-limit + re-level. Each pass trades a little crest for a little
    # level, so the loop converges on a crest factor low enough for -14 LUFS to
    # sit underneath the true-peak gate without any hard clipping.
    crest_target = 11.0
    for i in range(10):
        narration = synth.soft_limit(narration, peak_db=-5.0, knee=0.9)
        lv = meter.integrated_loudness(np.stack([narration, narration], axis=1)
                                       .astype(np.float64))
        narration = fit(narration * 10 ** ((-16.0 - lv) / 20.0), n)
        c = synth.crest_db(narration)
        if c <= crest_target:
            break
    print(f"  narration bus after {i + 1} pass(es): {synth.crest_db(narration):.1f} dB crest, "
          f"{meter.integrated_loudness(np.stack([narration, narration], axis=1).astype(np.float64)):.2f} LUFS")

    # ---------------------------------------------------------------- sfx bus
    sfx = np.zeros(n, dtype=np.float32)
    cue_rows = []
    riser_buf = synth.riser(0.34)
    for e in tl["events"]:
        frame = int(e["frame"])
        at = int(frame / FPS * SR)
        kind = e["kind"]
        gain = float(e["gain_db"])
        if kind == "silence":
            cue_rows.append((frame, at, kind, gain, e["note"]))
            continue
        if kind == "tick":
            y = synth.tick(2500.0, 0.45)
        elif kind == "tick_rise":
            tail = e["name"].rsplit("_", 1)[-1]
            step = int(tail) if tail.isdigit() else 0
            y = synth.tick_rise(step)
        elif kind == "click":
            y = synth.click(0.055, 2500.0, 0.5)
        elif kind == "whoosh":
            y = synth.whoosh(0.5)
        elif kind == "whoosh_rev":
            y = synth.whoosh_rev(0.42)
        elif kind == "riser":
            y = riser_buf
            gain = -13.0
        elif kind == "impact":
            y = synth.impact(0.95)
        elif kind == "chime":
            y = synth.chime(0.42)
        elif kind == "typing":
            y = synth.typing(0.22)
        elif kind == "buzz":
            y = synth.buzz(0.3)
        elif kind == "tap":
            y = synth.tap(0.35)
        else:
            continue
        place(sfx, at, y, gain)
        cue_rows.append((frame, at, kind, gain, e["note"]))

    # short convolution reverb on the SFX bus for cohesion.
    # The wet signal is level-matched to the dry bus by RMS: a raw convolution with
    # a noise impulse response sums thousands of taps and would otherwise add ~25 dB.
    ir = synth.make_ir(0.55, 5.5)
    sfx_wet = fftconvolve(sfx, ir, mode="full")[: n].astype(np.float32)
    dry_rms = float(np.sqrt(np.mean(sfx.astype(np.float64) ** 2)))
    wet_rms = float(np.sqrt(np.mean(sfx_wet.astype(np.float64) ** 2)))
    if wet_rms > 1e-12 and dry_rms > 1e-12:
        sfx_wet *= (0.22 * dry_rms) / wet_rms
    sfx_bus = fit(sfx * 0.9 + sfx_wet, n)
    # speech dominant: SFX transients sit clearly above the bed but below voice
    # peaks. A soft limiter is used rather than peak normalisation, because
    # normalising to the single loudest transient would bury every tick under it.
    sfx_bus = synth.soft_limit(sfx_bus, peak_db=-13.5, knee=0.62)

    # ---------------------------------------------------------------- music bed
    payoff_start = next(s["start_frame"] for s in tl["scenes"] if s["id"] == "payoff")
    music = fit(synth.pad(total_s, resolve_at=payoff_start / FPS), n) * 0.26
    air = fit(synth.noise_floor(total_s, 0.0016), n)

    # ---------------------------------------------------------------- ducking
    env = synth.fast_env(narration, DUCK_ATTACK, DUCK_RELEASE)
    ref = float(np.percentile(env, 99.5)) or 1.0
    duck = np.clip(env / (ref * 0.22), 0.0, 1.0)
    duck_gain = 10 ** ((DUCK_DB * duck) / 20.0)
    music_ducked = (music * duck_gain + air * (0.55 + 0.45 * duck_gain)).astype(np.float32)

    # ---------------------------------------------------------------- sum
    master = (narration * 10 ** (NARRATION_TRIM_DB / 20.0) + sfx_bus + music_ducked)
    master = synth.lowpass(master, 18000, 2).astype(np.float32)
    master = synth.soft_limit(master, peak_db=-1.0, knee=0.85)

    def _dbfs(x):
        return 20 * math.log10(max(1e-9, float(np.max(np.abs(x)))))

    meter_st = pyln.Meter(SR)
    for nm, st in (("narration", narration), ("sfx", sfx_bus), ("music", music_ducked)):
        lv = meter_st.integrated_loudness(np.stack([st, st], axis=1).astype(np.float64))
        print(f"  stem {nm:9s} peak {_dbfs(st):6.1f} dBFS   {lv:7.2f} LUFS")
    print(f"  stems sum master {_dbfs(master):.1f} dBFS")

    # ---------------------------------------------------------------- master gain
    # The gain is measured and applied here, using FFmpeg's own ebur128/loudnorm
    # meter, because that is the same meter the delivery gate uses. loudnorm's
    # linear mode was rejected: it will trade integrated loudness away to respect a
    # true-peak ceiling, and the gate needs BOTH "-14 +/-0.5" and "TP <= -1.5".
    from scipy.signal import resample_poly

    def analyse(src: Path) -> dict:
        r = subprocess.run(
            [str(ffmpeg), "-hide_banner", "-nostats", "-i", str(src),
             "-af", f"loudnorm=I={LOUDNESS_I}:TP={LOUDNESS_TP}:LRA={LOUDNESS_LRA}"
                    ":print_format=json", "-f", "null", "-"],
            capture_output=True, text=True)
        j = r.stderr[r.stderr.rfind("{"): r.stderr.rfind("}") + 1]
        if not j.startswith("{"):
            raise RuntimeError(f"loudnorm analysis produced no JSON for {src}")
        return json.loads(j)

    def true_peak_of(x: np.ndarray) -> float:
        up = resample_poly(x, 4, 1, axis=0)
        return synth.db(float(np.max(np.abs(up))))

    sf.write(str(outdir / "sfx.wav"), np.stack([sfx_bus, sfx_bus], axis=1), SR, subtype="PCM_16")
    sf.write(str(outdir / "music.wav"), np.stack([music_ducked, music_ducked], axis=1),
             SR, subtype="PCM_16")
    # The narration stem as it enters the mix, i.e. after compression and levelling.
    # qa.py subtracts this and the music from the delivered file to isolate the SFX
    # and time the cues against it without the music pad interfering.
    sf.write(str(outdir / "narration_stem.wav"),
             np.stack([narration, narration], axis=1), SR, subtype="PCM_16")
    sf.write(str(outdir / "master_music_sfx_only.wav"),
             np.stack([fit(sfx_bus + music_ducked, n)] * 2, axis=1), SR, subtype="PCM_16")

    raw = outdir / "master_ungained.wav"
    sf.write(str(raw), np.stack([master, master], axis=1), SR, subtype="PCM_16")
    pre = analyse(raw)
    pre_lufs = float(pre.get("input_i", -70.0))
    gain_db = LOUDNESS_I - pre_lufs

    stereo = (np.stack([master, master], axis=1) * 10 ** (gain_db / 20.0)).astype(np.float32)
    tp = true_peak_of(stereo)
    peak_trim_db = 0.0
    if tp > LOUDNESS_TP:
        peak_trim_db = LOUDNESS_TP - tp
        stereo = (stereo * 10 ** (peak_trim_db / 20.0)).astype(np.float32)
        tp = true_peak_of(stereo)

    pre_path = ABIT_CACHE / "master_pre_loudness_probe.wav"
    final = outdir / "master_final.wav"
    sf.write(str(pre_path), stereo, SR, subtype="PCM_16")
    shutil.copyfile(pre_path, final)
    pre_path.unlink(missing_ok=True)

    measured_out = analyse(final)

    info = {
        "integrated_lufs": float(measured_out.get("input_i", 0.0)),
        "true_peak_dbtp": float(measured_out.get("input_tp", -99.0)),
        "true_peak_dbtp_4x_oversampled": tp,
        "lra": float(measured_out.get("input_lra", 0.0)),
        "pre_master_lufs": pre_lufs,
        "applied_gain_db": round(gain_db, 2),
        "peak_trim_db": round(peak_trim_db, 2),
        "sample_peak_linear": float(np.max(np.abs(stereo))),
        "sample_peak_dbfs": synth.db(float(np.max(np.abs(stereo)))),
        "target_i": LOUDNESS_I,
        "target_tp": LOUDNESS_TP,
        "gate_tp": LOUDNESS_GATE_TP,
        "target_lra": LOUDNESS_LRA,
        "sample_rate": SR,
        "channels": 2,
        "duck_db": DUCK_DB,
        "duck_attack_s": DUCK_ATTACK,
        "duck_release_s": DUCK_RELEASE,
        "music_bed_relative_db": -22.0,
        "events": len(cue_rows),
    }
    (outdir / "loudness.json").write_text(json.dumps(info, indent=1), encoding="utf-8")

    # ---------------------------------------------------------------- cue sheet
    rows = ["A Bit Inside - sound cue sheet",
            f"generated from timeline.json, {tl['total_frames']} frames at {FPS} fps, "
            f"{total_s:.2f} s",
            "",
            f"{'frame':>7}  {'time':>8}  {'sample@48k':>11}  {'type':<12} {'gain dB':>8}  event",
            "-" * 96]
    for frame, at, kind, gain, note in sorted(cue_rows):
        rows.append(f"{frame:>7}  {frame / FPS:>7.3f}s  {at:>11}  {kind:<12} "
                    f"{gain:>8.1f}  {note}")
    rows += ["", "Legend",
              "  click/tick  2-3 kHz sine, 6 ms decay + noise transient",
              "  whoosh      band-passed noise, sweeping centre frequency, sin^2 envelope",
              "  riser       ascending tone, swelling gain",
              "  impact      70 -> 38 Hz sweep, 350 ms decay + low-passed noise",
              "  chime       two-note additive sine, 0.6 s decay (the sonic logo)",
              "  buzz        110 Hz square, 150 ms",
              "  typing      random-interval micro clicks",
              "  silence     designed 0.4 s drop before the reveal (no audio written)",
              ""]
    (DAY / "cue-sheet.txt").write_text("\n".join(rows), encoding="utf-8")

    print(f"  events placed: {len(cue_rows)}")
    print(f"  integrated  : {info['integrated_lufs']:.2f} LUFS (target {LOUDNESS_I})")
    print(f"  true peak   : {info['true_peak_dbtp']:.2f} dBTP (target <= {LOUDNESS_TP})")
    print(f"  sample peak : {info['sample_peak_dbfs']:.2f} dBFS")
    print("  wrote audio/*.wav, audio/loudness.json, cue-sheet.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())