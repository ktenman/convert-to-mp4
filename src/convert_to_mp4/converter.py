from __future__ import annotations

import shutil
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from convert_to_mp4.audio import AudioInfo, calculate_optimal_bitrate, should_reencode
from convert_to_mp4.ffmpeg import (
    LoudnessStats,
    ProbeResult,
    build_loudnorm_filter,
    measure_loudness,
    probe,
    run_conversion,
)

VIDEO_EXTENSIONS = {
    ".mkv",
    ".avi",
    ".mov",
    ".mp4",
    ".webm",
    ".flv",
    ".wmv",
    ".mpg",
    ".mpeg",
    ".m4v",
    ".3gp",
}

FALLBACK_PARAMS = [
    "-c:v",
    "libx264",
    "-preset",
    "fast",
    "-crf",
    "23",
    "-c:a",
    "aac",
    "-ac",
    "2",
    "-b:a",
    "192k",
    "-movflags",
    "+faststart",
]

console = Console()


@dataclass
class ConversionOptions:
    quality: int | None = None
    min_quality: int = 128
    max_quality: int = 256
    force_audio: bool = False
    normalize: bool = True
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
    files = [f for f in glob_fn("*") if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS]
    return sorted(files)


def _is_already_compatible(probe_result: ProbeResult, file_path: Path) -> bool:
    if file_path.suffix.lower() != ".mp4":
        return False
    return (
        probe_result.video_codec == "h264"
        and probe_result.audio_codec == "aac"
        and probe_result.audio_channels <= 2
    )


def _needs_audio_reencode(probe_result: ProbeResult, options: ConversionOptions) -> bool:
    audio_info = AudioInfo(
        codec=probe_result.audio_codec,
        channels=probe_result.audio_channels,
        bitrate=probe_result.audio_bitrate,
    )
    return should_reencode(audio_info, options.force_audio) or options.quality is not None


def _build_ffmpeg_params(
    probe_result: ProbeResult,
    options: ConversionOptions,
    loudness: LoudnessStats | None,
) -> list[str]:
    params = ["-c:v", "copy"]

    if _needs_audio_reencode(probe_result, options):
        if options.quality is not None:
            target_bitrate = options.quality
        else:
            target_bitrate = calculate_optimal_bitrate(
                probe_result.audio_bitrate,
                probe_result.audio_codec,
                options.min_quality,
                options.max_quality,
            )
        params.extend(["-c:a", "aac"])
        if loudness is not None:
            params.extend(["-af", build_loudnorm_filter(loudness)])
        else:
            params.extend(["-ac", "2"])
        params.extend(["-b:a", f"{target_bitrate}k"])
    else:
        params.extend(["-c:a", "copy"])

    params.extend(["-movflags", "+faststart"])
    return params


def _run_with_retries(
    file_path: Path,
    output_path: Path,
    params: list[str],
    duration: float,
    on_progress: Callable[[float], None] | None,
) -> bool:
    attempts = [
        params,
        [*params, "-err_detect", "ignore_err"],
        FALLBACK_PARAMS,
    ]

    for attempt_params in attempts:
        if on_progress:
            on_progress(0.0)
        success = run_conversion(
            input_path=file_path,
            output_path=output_path,
            params=attempt_params,
            duration=duration,
            on_progress=on_progress,
        )
        if success:
            return True

    return False


def convert_file(
    file_path: Path,
    options: ConversionOptions,
    on_progress: Callable[[float], None] | None = None,
) -> ConversionResult:
    final_output = file_path.with_suffix(".mp4")
    is_same_path = file_path.resolve() == final_output.resolve()
    temp_output = file_path.with_suffix(".converting.mp4") if is_same_path else final_output
    input_size = file_path.stat().st_size

    result = ConversionResult(
        input_path=file_path,
        output_path=final_output,
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

    loudness = None
    if options.normalize and _needs_audio_reencode(probe_result, options):
        loudness = measure_loudness(file_path)

    params = _build_ffmpeg_params(probe_result, options, loudness)
    start = time.monotonic()

    success = _run_with_retries(
        file_path,
        temp_output,
        params,
        probe_result.duration,
        on_progress,
    )

    if success:
        if is_same_path:
            temp_output.replace(final_output)
        result.elapsed = time.monotonic() - start
        result.success = True
        result.output_size = final_output.stat().st_size
        return result

    result.elapsed = time.monotonic() - start
    result.success = False
    result.error = "all conversion attempts failed"
    temp_output.unlink(missing_ok=True)
    return result


def convert_single(file_path: Path, options: ConversionOptions) -> ConversionResult:
    console.print(f"Converting [cyan]{file_path.name}[/cyan]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(file_path.name, total=100.0)

        def on_progress(percentage: float) -> None:
            progress.update(task, completed=percentage)

        result = convert_file(file_path, options, on_progress=on_progress)
        progress.update(task, completed=100.0)

    if result.skipped:
        console.print(f"[yellow]Skipped ({result.skip_reason})[/yellow]")
    elif result.success:
        saved = result.input_size - result.output_size
        console.print(
            f"[green]Done[/green] in {result.elapsed:.1f}s "
            f"({result.input_size // 1024}K -> {result.output_size // 1024}K, "
            f"saved {saved // 1024}K)"
        )
    else:
        console.print(f"[red]Failed: {result.error}[/red]")

    return result


def convert_directory(directory: Path, options: ConversionOptions) -> list[ConversionResult]:
    files = find_video_files(directory, options.recursive)

    if not files:
        console.print(f"No video files found in {directory}")
        return []

    console.print(f"Found [green]{len(files)}[/green] video file(s) to process")

    results = []

    if options.jobs > 1:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold green]{task.description}"),
            BarColumn(bar_width=40),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            overall = progress.add_task("Overall", total=len(files))

            with ThreadPoolExecutor(max_workers=options.jobs) as executor:
                futures = {executor.submit(convert_file, f, options): f for f in files}
                for future in as_completed(futures):
                    results.append(future.result())
                    progress.advance(overall)
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            overall = progress.add_task("Overall", total=len(files))

            for file_path in files:
                file_task = progress.add_task(file_path.name, total=100.0)

                def on_progress(percentage: float, _task=file_task) -> None:
                    progress.update(_task, completed=percentage)

                result = convert_file(file_path, options, on_progress=on_progress)
                progress.update(file_task, completed=100.0, visible=False)
                progress.advance(overall)
                results.append(result)

    return results
