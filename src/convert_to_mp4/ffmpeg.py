"""FFmpeg/ffprobe wrapper with imageio-ffmpeg integration."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProbeResult:
    """Result of probing a media file."""

    video_codec: str
    audio_codec: str
    audio_bitrate: int  # bps (0 if unknown)
    audio_channels: int
    duration: float  # seconds


def get_ffmpeg_path() -> str:
    """Get path to ffmpeg binary. Prefers imageio-ffmpeg bundle, falls back to system."""
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


def get_ffprobe_path() -> str:
    """Get path to ffprobe binary.

    imageio-ffmpeg only bundles ffmpeg, not ffprobe. Strategy:
    1. Look for ffprobe next to the bundled ffmpeg binary
    2. Fall back to system ffprobe
    """
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
    """Probe a media file and return stream information."""
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
    """Run ffmpeg conversion with progress tracking.

    Returns True on success, False on failure.
    """
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

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    while True:
        line = process.stdout.readline()
        if not line:
            break

        decoded = line.decode("utf-8", errors="replace").strip()

        if decoded.startswith("out_time_us=") and on_progress and duration > 0:
            try:
                time_us = int(decoded.split("=")[1])
                percentage = min(time_us / (duration * 1_000_000) * 100, 100.0)
                on_progress(percentage)
            except (ValueError, ZeroDivisionError):
                pass

        if decoded == "progress=end":
            break

    return_code = process.wait()
    return return_code == 0
