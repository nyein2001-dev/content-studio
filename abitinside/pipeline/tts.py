"""Narration with Microsoft Andrew only, through the free edge-tts client.

A missing voice, a failed call, or a request for any other voice stops the job.
Cached audio is reused only when the voice, the rate, and the text all match.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import pyloudnorm as pyln  # noqa: E402
import soundfile as sf  # noqa: E402

from pipeline.config import (  # noqa: E402
    GAP_AFTER_DEFAULT,
    GAP_BEFORE_ENDCARD,
    GAP_BEFORE_REVEAL,
    LEAD_IN_S,
    RATE_CHOICES,
    ROOT,
    SENTENCE_LUFS,
    SPEECH_RATE,
    TARGET_MAX_S,
    TARGET_MIN_S,
    TARGET_SR,
    TTS_PROVIDER,
    VOICE_ID,
    require_voice,
)

CACHE = ROOT / ".cache" / "tts"


def gap_after(scene_id: str) -> float:
    if scene_id == "the_gap":
        return GAP_BEFORE_REVEAL
    if scene_id == "question":
        return GAP_BEFORE_ENDCARD
    return GAP_AFTER_DEFAULT


def _cache_key(text: str, rate: str) -> str:
    blob = f"{TTS_PROVIDER}|{VOICE_ID}|{rate}|{text}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _ffmpeg() -> str:
    import os
    return os.environ.get("FFMPEG", str(ROOT / "tools" / "ffmpeg" / "bin" / "ffmpeg"))


def _ticks_to_seconds(value: float) -> float:
    # edge-tts reports offsets in 100-nanosecond ticks. A value already in seconds
    # for a single word is well under 20.
    if value > 50:
        return value / 10_000_000.0
    return float(value)


async def _list_short_names() -> set[str]:
    import edge_tts

    voices = await edge_tts.list_voices()
    return {v["ShortName"] for v in voices}


async def ensure_voice() -> None:
    require_voice(VOICE_ID)
    last: Exception | None = None
    for attempt in range(5):
        try:
            names = await _list_short_names()
            if VOICE_ID not in names:
                raise SystemExit(
                    f"{VOICE_ID} is not in the {TTS_PROVIDER} voice list. Stopping. "
                    "No fallback voice will be used."
                )
            return
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001 - DNS blips are retried, then the job stops
            last = exc
            await asyncio.sleep(3 * (attempt + 1))
    raise SystemExit(
        f"{TTS_PROVIDER} could not list voices ({type(last).__name__}: {last}). "
        "Stopping. No other voice will be used."
    )


async def _stream(text: str, rate: str) -> tuple[bytes, list[dict]]:
    import edge_tts

    require_voice(VOICE_ID)
    communicate = edge_tts.Communicate(
        text, VOICE_ID, rate=rate, boundary="WordBoundary")
    audio = bytearray()
    words: list[dict] = []
    async for chunk in communicate.stream():
        kind = chunk["type"]
        if kind == "audio":
            audio.extend(chunk["data"])
        elif kind == "WordBoundary":
            start = _ticks_to_seconds(float(chunk["offset"]))
            dur = _ticks_to_seconds(float(chunk["duration"]))
            words.append({
                "text": chunk["text"],
                "t_start": round(start, 4),
                "t_end": round(start + dur, 4),
            })
    if not audio or not words:
        raise SystemExit(f"{VOICE_ID} returned no audio or no word boundaries for: {text[:60]!r}")
    return bytes(audio), words


def _decode(mp3: bytes) -> np.ndarray:
    cmd = [
        _ffmpeg(), "-hide_banner", "-loglevel", "error",
        "-f", "mp3", "-i", "pipe:0",
        "-f", "f32le", "-ac", "1", "-ar", str(TARGET_SR), "pipe:1",
    ]
    proc = subprocess.run(cmd, input=mp3, capture_output=True)
    if proc.returncode != 0 or not proc.stdout:
        raise SystemExit(f"ffmpeg could not decode Andrew audio: {proc.stderr[:300]!r}")
    audio = np.frombuffer(proc.stdout, dtype=np.float32).copy()
    if audio.size < TARGET_SR // 10:
        raise SystemExit("Andrew utterance is too short to be speech")
    return audio


def _attach_punctuation(script: str, words: list[dict]) -> list[dict]:
    """Keep the script's commas and apostrophes when the spoken tokens match."""
    import re

    tokens = re.findall(r"\S+", script)
    if len(tokens) != len(words):
        return words
    attached = []
    for token, word in zip(tokens, words):
        core = re.sub(r"[^\w']+", "", token)
        spoken = re.sub(r"[^\w']+", "", word["text"])
        if core.lower() == spoken.lower():
            attached.append({**word, "text": token})
        else:
            attached.append(word)
    return attached


def _prepare(audio: np.ndarray, words: list[dict]) -> tuple[np.ndarray, list[dict], float]:
    idx = np.where(np.abs(audio) > 0.004)[0]
    if len(idx):
        cut = max(0, int(idx[0]) - int(0.01 * TARGET_SR))
    else:
        cut = 0
    shift = cut / TARGET_SR
    audio = audio[cut:]
    shifted = []
    for word in words:
        start = max(0.0, word["t_start"] - shift)
        end = max(start + 0.02, word["t_end"] - shift)
        shifted.append({"text": word["text"], "t_start": round(start, 4), "t_end": round(end, 4)})
    meter = pyln.Meter(TARGET_SR)
    loud = meter.integrated_loudness(audio.astype(np.float64))
    if np.isfinite(loud):
        audio = audio * (10 ** ((SENTENCE_LUFS - loud) / 20))
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    ceiling = 10 ** (-3.0 / 20)
    if peak > ceiling:
        audio = audio * (ceiling / peak)
    return audio.astype(np.float32), shifted, float(loud if np.isfinite(loud) else -99.0)


def synthesise(text: str, rate: str = SPEECH_RATE) -> tuple[np.ndarray, list[dict], float]:
    """Return 48 kHz audio, word times relative to that audio, and pre-gain LUFS."""
    require_voice(VOICE_ID)
    CACHE.mkdir(parents=True, exist_ok=True)
    key = _cache_key(text, rate)
    wav_path = CACHE / f"{key}.wav"
    meta_path = CACHE / f"{key}.json"
    if wav_path.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("voice") != VOICE_ID or meta.get("text") != text or meta.get("rate") != rate:
            raise SystemExit(f"cache {key} does not match {VOICE_ID!r} / this text; refusing to reuse it")
        audio, sr = sf.read(str(wav_path), dtype="float32")
        if sr != TARGET_SR:
            raise SystemExit(f"cached narration is {sr} Hz, expected {TARGET_SR}")
        if getattr(audio, "ndim", 1) > 1:
            audio = audio.mean(axis=1)
        return audio.astype(np.float32), meta["words"], float(meta["lufs_before"])
    last_error: Exception | None = None
    for _attempt in range(3):
        try:
            mp3, words = asyncio.run(_stream(text, rate))
            audio, words, loud = _prepare(_decode(mp3), words)
            words = _attach_punctuation(text, words)
            sf.write(str(wav_path), audio, TARGET_SR, subtype="PCM_16")
            meta_path.write_text(json.dumps({
                "voice": VOICE_ID,
                "provider": TTS_PROVIDER,
                "rate": rate,
                "text": text,
                "words": words,
                "lufs_before": loud,
            }), encoding="utf-8")
            return audio, words, loud
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001 - retry transient network faults, then stop
            last_error = exc
    raise SystemExit(
        f"{VOICE_ID} failed for {text[:60]!r} ({type(last_error).__name__}: {last_error}). "
        "Stopping. No fallback voice will be used."
    )


def _lines(plan: dict) -> list[tuple[str, int, str]]:
    rows = []
    for scene in plan["scenes"]:
        for index, line in enumerate(scene["sentences"]):
            rows.append((scene["id"], index, line))
    return rows


def _assemble(parts: list[dict], rate: str) -> dict:
    lead = int(LEAD_IN_S * TARGET_SR)
    gaps = [gap_after(p["scene"]) for p in parts]
    total = lead + sum(p["audio"].size for p in parts) + sum(int(g * TARGET_SR) for g in gaps)
    track = np.zeros(total, dtype=np.float32)
    cursor = lead
    records = []
    for part, gap in zip(parts, gaps):
        track[cursor:cursor + part["audio"].size] = part["audio"]
        records.append({
            "scene": part["scene"],
            "index": part["index"],
            "text": part["text"],
            "voice": VOICE_ID,
            "provider": TTS_PROVIDER,
            "rate": rate,
            "samples": int(part["audio"].size),
            "seconds": round(part["audio"].size / TARGET_SR, 3),
            "lufs_before": round(part["lufs"], 2),
            "start_sample": int(cursor),
            "start_seconds": round(cursor / TARGET_SR, 3),
            "gap_after_seconds": gap,
            "words": part["words"],
        })
        cursor += part["audio"].size + int(gap * TARGET_SR)
    return {"track": track, "records": records, "seconds": track.size / TARGET_SR}


def render_day(day: Path, rate: str | None = None) -> Path:
    asyncio.run(ensure_voice())
    plan = json.loads((day / "scenes_plan.json").read_text(encoding="utf-8"))
    lines = _lines(plan)
    order = [rate] if rate else list(RATE_CHOICES)
    # Prefer the configured moderate rate, then the neighbours, staying inside the list.
    if rate is None:
        order = [SPEECH_RATE] + [r for r in RATE_CHOICES if r != SPEECH_RATE]
    chosen = None
    built = None
    for candidate in order:
        require_voice(VOICE_ID)
        parts = []
        print(f"synthesising {len(lines)} sentences with {VOICE_ID} at {candidate}")
        for scene, index, text in lines:
            audio, words, loud = synthesise(text, candidate)
            parts.append({
                "scene": scene, "index": index, "text": text,
                "audio": audio, "words": words, "lufs": loud,
            })
        built = _assemble(parts, candidate)
        print(f"  rate {candidate} -> {built['seconds']:.2f} s")
        chosen = candidate
        if TARGET_MIN_S <= built["seconds"] <= TARGET_MAX_S:
            break
    assert built is not None and chosen is not None
    audio_dir = day / "audio"
    audio_dir.mkdir(exist_ok=True)
    sf.write(str(audio_dir / "narration.wav"), built["track"], TARGET_SR, subtype="PCM_16")
    meta = {
        "voice": VOICE_ID,
        "provider": TTS_PROVIDER,
        "rate": chosen,
        # Timeline records this. Duration is measured, not time-stretched.
        "length_scale": 1.0,
        "sample_rate": TARGET_SR,
        "delivery_rate": TARGET_SR,
        "narration_seconds": round(built["seconds"], 3),
        "narration_samples_48k": int(built["track"].size),
        "sentence_target_lufs": SENTENCE_LUFS,
        "sentences": built["records"],
    }
    path = day / "tts_sentences.json"
    path.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"wrote {path.name} voice={VOICE_ID} duration={built['seconds']:.2f}s")
    return path


def main(argv: list[str] | None = None) -> int:
    day = Path(sys.argv[1] if argv is None else argv[0]).resolve()
    render_day(day)
    return 0


if __name__ == "__main__":
    sys.exit(main())
