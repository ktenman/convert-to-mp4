"""CLI entry point using Typer."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from convert_to_mp4.converter import (
    ConversionOptions,
    ConversionResult,
    convert_directory,
    convert_file,
)
from convert_to_mp4.presets import Preset, get_preset_config

app = typer.Typer(
    name="convert-to-mp4",
    help="Smart video converter with automatic audio quality detection.",
    add_completion=False,
)
console = Console()


def generate_report(results: list[ConversionResult]) -> None:
    """Print summary table and save report file."""
    if not results:
        return

    table = Table(title="Conversion Summary")
    table.add_column("File", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Size", justify="right")
    table.add_column("Time", justify="right")

    success_count = 0
    total_saved = 0

    for r in results:
        if r.skipped:
            status = f"[yellow]Skipped ({r.skip_reason})[/yellow]"
            size_info = ""
            time_info = ""
        elif r.success:
            success_count += 1
            saved = r.input_size - r.output_size
            total_saved += saved
            status = "[green]OK[/green]"
            size_info = f"{r.input_size // 1024}K -> {r.output_size // 1024}K"
            time_info = f"{r.elapsed:.1f}s"
        else:
            status = f"[red]Failed: {r.error}[/red]"
            size_info = ""
            time_info = f"{r.elapsed:.1f}s"

        table.add_row(r.input_path.name, status, size_info, time_info)

    console.print(table)

    total = len([r for r in results if not r.skipped])
    if total > 0:
        console.print(f"\n[bold]{success_count}/{total}[/bold] converted successfully")
        if total_saved > 0:
            console.print(f"Total space saved: [green]{total_saved // 1024}K[/green]")

    # Save report file
    report_name = f"conversion_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_name, "w") as f:
        f.write(f"Conversion Report - {datetime.now()}\n")
        f.write(f"Total: {len(results)}, Success: {success_count}\n\n")
        for r in results:
            status = "OK" if r.success else ("SKIP" if r.skipped else "FAIL")
            f.write(f"  [{status}] {r.input_path}\n")

    console.print(f"Report saved to: [blue]{report_name}[/blue]")


def _validate_quality_range(min_q: int, max_q: int) -> None:
    if min_q > max_q:
        raise typer.BadParameter(
            f"--min-quality ({min_q}) cannot be greater than --max-quality ({max_q})"
        )


@app.command()
def _main(
    path: Annotated[
        Path,
        typer.Argument(help="File or directory to convert", exists=True),
    ] = Path("."),
    recursive: Annotated[
        bool,
        typer.Option("-r", "--recursive", help="Recurse into subdirectories"),
    ] = False,
    jobs: Annotated[
        int,
        typer.Option("-j", "--jobs", help="Parallel conversion jobs", min=1, max=32),
    ] = 1,
    quality: Annotated[
        Optional[int],
        typer.Option("-q", "--quality", help="Override audio bitrate (64-320)", min=64, max=320),
    ] = None,
    preset: Annotated[
        Optional[Preset],
        typer.Option("--preset", help="Predefined settings"),
    ] = None,
    min_quality: Annotated[
        int,
        typer.Option("--min-quality", help="Minimum audio bitrate", min=64, max=320),
    ] = 128,
    max_quality: Annotated[
        int,
        typer.Option("--max-quality", help="Maximum audio bitrate", min=64, max=320),
    ] = 256,
    force_audio: Annotated[
        bool,
        typer.Option("--force-audio", help="Force audio re-encoding"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be done"),
    ] = False,
) -> None:
    """Convert video files to browser-compatible MP4 with smart audio quality detection."""
    # Apply preset overrides
    if preset is not None:
        preset_config = get_preset_config(preset)
        min_quality = preset_config.min_quality
        max_quality = preset_config.max_quality
        console.print(f"[blue]Using {preset.value} preset: {preset_config.description}[/blue]")

    _validate_quality_range(min_quality, max_quality)

    options = ConversionOptions(
        quality=quality,
        min_quality=min_quality,
        max_quality=max_quality,
        force_audio=force_audio,
        dry_run=dry_run,
        recursive=recursive,
        jobs=jobs,
    )

    if path.is_file():
        result = convert_file(path, options)
        generate_report([result])
    else:
        results = convert_directory(path, options)
        generate_report(results)


def main() -> None:
    """Entry point for the CLI."""
    app()
