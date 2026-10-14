"""Compare encoded frames with the renderer."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from layout.errors import LayoutError
from layout.model import PlacedScene
from layout.render import render_frame
from layout.spec import load_spec


def ffmpeg_bin() -> str:
    import os
    env = os.environ.get("FFMPEG")
    if env and Path(env).is_file():
        return env
    bundled = Path(__file__).resolve().parents[1] / "tools" / "ffmpeg" / "bin" / "ffmpeg"
    if bundled.is_file():
        return str(bundled)
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise LayoutError(
        "encode", "LR-12",
        "ffmpeg was not found",
        "Run bash setup.sh so tools/ffmpeg is installed.",
    )


def write_video(scenes: list[PlacedScene], path: Path, preset: str | None = None) -> None:
    spec = load_spec()
    if not scenes:
        raise LayoutError("encode", "LR-13", "no scenes to encode", "Add a scene.")
    width, height = scenes[0].width, scenes[0].height
    fps = scenes[0].fps
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
        "-an", "-c:v", "libx264",
        "-profile:v", str(spec["encode"]["profile"]),
        "-level", str(spec["encode"]["level"]),
        "-pix_fmt", spec["encode"]["pixel_format"],
        "-crf", str(spec["encode"]["crf"]),
        "-preset", preset or spec["encode"]["preset"],
        "-tune", str(spec["encode"]["tune"]),
        "-g", str(spec["encode"]["gop"]),
        "-bf", str(spec["encode"]["bframes"]),
        "-colorspace", spec["encode"]["colorspace"],
        "-color_primaries", spec["encode"]["colorspace"],
        "-color_trc", spec["encode"]["colorspace"],
        str(path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for scene in scenes:
            for frame in range(scene.duration_frames):
                image = render_frame(scene, frame).convert("RGB")
                proc.stdin.write(image.tobytes())
    finally:
        proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
    code = proc.wait()
    if code != 0:
        raise LayoutError("encode", "LR-12", f"ffmpeg failed: {err[-500:]}", "Fix the encoder error and rerun the gate.")


def psnr(left: Image.Image, right: Image.Image) -> float:
    a = np.asarray(left.convert("RGB"), dtype=np.float32)
    b = np.asarray(right.convert("RGB"), dtype=np.float32)
    if a.shape != b.shape:
        raise LayoutError("parity", "LR-12", f"frame size {a.shape} != {b.shape}", "Encode at the scene canvas size.")
    mse = float(np.mean((a - b) ** 2))
    if mse <= 1e-8:
        return 99.0
    return 10.0 * np.log10((255.0 ** 2) / mse)


def check_parity(
    scene: PlacedScene,
    video: Path,
    frames: list[int] | None = None,
    video_offset: int = 0,
) -> list:
    from layout.rules import Violation
    spec = load_spec()
    frames = frames or [0, scene.duration_frames // 2, max(0, scene.duration_frames - 1)]
    found = []
    floor = float(spec["rules"]["psnr_min"])
    for frame in frames:
        decoded = _decode(video, video_offset + frame, scene.width, scene.height)
        rendered = render_frame(scene, frame)
        score = psnr(rendered, decoded)
        if score < floor:
            found.append(Violation(
                scene.scene_id, "LR-12", "fail",
                f"frame {frame} PSNR {score:.1f} is below {floor}",
                "The encoded file does not match the renderer. Do not publish it.",
                frame=frame, measured={"psnr": score},
            ))
    return found


def _decode(video: Path, frame: int, width: int, height: int) -> Image.Image:
    cmd = [
        ffmpeg_bin(), "-v", "error", "-i", str(video),
        "-vf", f"select=eq(n\\,{frame})", "-vframes", "1",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ]
    proc = subprocess.run(cmd, check=False, capture_output=True)
    if proc.returncode != 0 or len(proc.stdout) < width * height * 3:
        raise LayoutError(
            "parity", "LR-12",
            f"could not decode frame {frame}",
            "Re-encode the draft. A frame the renderer cannot read back cannot be published.",
        )
    return Image.frombytes("RGB", (width, height), proc.stdout[: width * height * 3])
