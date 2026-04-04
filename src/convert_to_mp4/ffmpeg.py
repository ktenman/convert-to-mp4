from __future__ import annotations

import functools
import json
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProbeResult:
    video_codec: str
    audio_codec: str
    audio_bitrate: int
    audio_channels: int
    duration: float


@functools.lru_cache(maxsize=1)
def get_ffmpeg_path() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass

    system_path = shutil.which("ffmpeg")
    if system_path:
        return system_path

    raise RuntimeError(
        "ffmpeg not found. Install via: pip install imageio-ffmpeg, "
        "or install ffmpeg on your system."
    )


@functools.lru_cache(maxsize=1)
def get_ffprobe_path() -> str:
    ffmpeg_path = get_ffmpeg_path()
    ffprobe_candidate = Path(ffmpeg_path).parent / "ffprobe"
    if ffprobe_candidate.is_file():
        return str(ffprobe_candidate)

    system_path = shutil.which("ffprobe")
    if system_path:
        return system_path

    raise RuntimeError(
        "ffprobe not found. Install ffmpeg/ffprobe on your system."
    )


def probe(file_path: Path) -> ProbeResult:
    ffprobe = get_ffprobe_path()
    result = subprocess.run(
        [
            ffprobe,
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-show_format",
            str(file_path),
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {file_path}: {result.stderr}")

    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    fmt = data.get("format", {})

    video_codec = ""
    audio_codec = ""
    audio_bitrate = 0
    audio_channels = 0

    for stream in streams:
        codec_type = stream.get("codec_type")
        if codec_type == "video" and not video_codec:
            video_codec = stream.get("codec_name", "")
        elif codec_type == "audio" and not audio_codec:
            audio_codec = stream.get("codec_name", "")
            audio_bitrate = int(stream.get("bit_rate", 0) or 0)
            audio_channels = int(stream.get("channels", 0) or 0)

    duration = float(fmt.get("duration", 0) or 0)

    return ProbeResult(
        video_codec=video_codec,
        audio_codec=audio_codec,
        audio_bitrate=audio_bitrate,
        audio_channels=audio_channels,
        duration=duration,
    )


def run_conversion(
    input_path: Path,
    output_path: Path,
    params: list[str],
    duration: float,
    on_progress: Callable[[float], None] | None,
) -> bool:
    ffmpeg = get_ffmpeg_path()
    cmd = [
        ffmpeg,
        "-i", str(input_path),
        *params,
        "-progress", "pipe:1",
        "-nostats",
        "-y",
        str(output_path),
    ]

    stderr_target = subprocess.PIPE if on_progress is None else subprocess.DEVNULL

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=stderr_target,
    )

    if on_progress is None:
        process.communicate()
    else:
        while True:
            line = process.stdout.readline()
            if not line:
                break

            decoded = line.decode("utf-8", errors="replace").strip()

            if decoded.startswith("out_time_us=") and duration > 0:
                try:
                    time_us = int(decoded.split("=")[1])
                    percentage = min(time_us / (duration * 1_000_000) * 100, 100.0)
                    on_progress(percentage)
                except (ValueError, ZeroDivisionError):
                    pass

            if decoded == "progress=end":
                break

    return process.wait() == 0
