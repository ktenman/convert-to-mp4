from __future__ import annotations

import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from convert_to_mp4.audio import AudioInfo, calculate_optimal_bitrate, should_reencode
from convert_to_mp4.ffmpeg import probe, run_conversion

VIDEO_EXTENSIONS = {
    ".mkv", ".avi", ".mov", ".mp4", ".webm",
    ".flv", ".wmv", ".mpg", ".mpeg", ".m4v", ".3gp",
}

console = Console()


@dataclass
class ConversionOptions:
    quality: int | None = None
    min_quality: int = 128
    max_quality: int = 256
    force_audio: bool = False
    dry_run: bool = False
    recursive: bool = False
    jobs: int = 1


@dataclass
class ConversionResult:
    input_path: Path
    output_path: Path
    input_size: int = 0
    output_size: int = 0
    duration: float = 0.0
    elapsed: float = 0.0
    success: bool = False
    error: str | None = None
    skipped: bool = False
    skip_reason: str | None = None


def check_disk_space(directory: Path, file_size: int) -> bool:
    usage = shutil.disk_usage(directory)
    required = int(file_size * 1.5)
    return usage.free >= required


def find_video_files(directory: Path, recursive: bool) -> list[Path]:
    glob_fn = directory.rglob if recursive else directory.glob
    files = [
        f for f in glob_fn("*")
        if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
    ]
    return sorted(files)


def _is_already_compatible(probe_result, file_path: Path) -> bool:
    if file_path.suffix.lower() != ".mp4":
        return False
    return (
        probe_result.video_codec == "h264"
        and probe_result.audio_codec == "aac"
        and probe_result.audio_channels <= 2
    )


def _build_ffmpeg_params(probe_result, options: ConversionOptions) -> list[str]:
    params = ["-c:v", "copy"]

    audio_info = AudioInfo(
        codec=probe_result.audio_codec,
        channels=probe_result.audio_channels,
        bitrate=probe_result.audio_bitrate,
    )

    if should_reencode(audio_info, options.force_audio) or options.quality is not None:
        if options.quality is not None:
            target_bitrate = options.quality
        else:
            target_bitrate = calculate_optimal_bitrate(
                probe_result.audio_bitrate,
                probe_result.audio_codec,
                options.min_quality,
                options.max_quality,
            )
        params.extend(["-c:a", "aac", "-ac", "2", "-b:a", f"{target_bitrate}k"])
    else:
        params.extend(["-c:a", "copy"])

    params.extend(["-movflags", "+faststart"])
    return params


def convert_file(file_path: Path, options: ConversionOptions) -> ConversionResult:
    output_path = file_path.with_suffix(".mp4")
    input_size = file_path.stat().st_size

    result = ConversionResult(
        input_path=file_path,
        output_path=output_path,
        input_size=input_size,
    )

    probe_result = probe(file_path)
    result.duration = probe_result.duration

    if _is_already_compatible(probe_result, file_path):
        result.skipped = True
        result.skip_reason = "already compatible"
        result.success = True
        return result

    if options.dry_run:
        result.skipped = True
        result.skip_reason = "dry run"
        return result

    if not check_disk_space(file_path.parent, input_size):
        result.success = False
        result.error = "insufficient disk space"
        return result

    params = _build_ffmpeg_params(probe_result, options)

    start = time.monotonic()
    attempts = [
        params,
        [*params, "-err_detect", "ignore_err"],
        ["-c:v", "libx264", "-preset", "fast", "-crf", "23",
         "-c:a", "aac", "-ac", "2", "-b:a", "192k",
         "-movflags", "+faststart"],
    ]

    for attempt_params in attempts:
        success = run_conversion(
            input_path=file_path,
            output_path=output_path,
            params=attempt_params,
            duration=probe_result.duration,
            on_progress=None,
        )
        if success:
            result.elapsed = time.monotonic() - start
            result.success = True
            result.output_size = output_path.stat().st_size
            return result

    result.elapsed = time.monotonic() - start
    result.success = False
    result.error = "all conversion attempts failed"
    output_path.unlink(missing_ok=True)
    return result


def convert_directory(directory: Path, options: ConversionOptions) -> list[ConversionResult]:
    files = find_video_files(directory, options.recursive)

    if not files:
        console.print(f"No video files found in {directory}")
        return []

    console.print(f"Found [green]{len(files)}[/green] video file(s) to process")

    results = []
    if options.jobs > 1:
        with ThreadPoolExecutor(max_workers=options.jobs) as executor:
            futures = {
                executor.submit(convert_file, f, options): f for f in files
            }
            for future in as_completed(futures):
                results.append(future.result())
    else:
        for file_path in files:
            result = convert_file(file_path, options)
            results.append(result)

    return results
