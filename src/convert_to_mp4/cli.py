from __future__ import annotations

import json
import logging
import subprocess
import urllib.error
import urllib.request
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import typer
from packaging.version import Version
from rich.console import Console
from rich.table import Table

from convert_to_mp4.converter import (
    ConversionOptions,
    ConversionResult,
    convert_directory,
    convert_single,
)
from convert_to_mp4.presets import Preset, get_preset_config

logger = logging.getLogger(__name__)

GITHUB_REPO = "ktenman/convert-to-mp4"

app = typer.Typer(
    name="convert-to-mp4",
    help="Smart video converter with automatic audio quality detection.",
    add_completion=False,
)
console = Console()


def generate_report(results: list[ConversionResult], *, dry_run: bool = False) -> None:
    if not results:
        return

    table = Table(title="Conversion Summary")
    table.add_column("File", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Size", justify="right")
    table.add_column("Time", justify="right")

    success_count = 0
    total_saved = 0
    non_skipped_count = 0

    for r in results:
        if r.skipped:
            status = f"[yellow]Skipped ({r.skip_reason})[/yellow]"
            size_info = ""
            time_info = ""
        elif r.success:
            success_count += 1
            non_skipped_count += 1
            saved = r.input_size - r.output_size
            total_saved += saved
            status = "[green]OK[/green]"
            size_info = f"{r.input_size // 1024}K -> {r.output_size // 1024}K"
            time_info = f"{r.elapsed:.1f}s"
        else:
            non_skipped_count += 1
            status = f"[red]Failed: {r.error}[/red]"
            size_info = ""
            time_info = f"{r.elapsed:.1f}s"

        table.add_row(r.input_path.name, status, size_info, time_info)

    console.print(table)

    if non_skipped_count > 0:
        console.print(f"\n[bold]{success_count}/{non_skipped_count}[/bold] converted successfully")
        if total_saved > 0:
            console.print(f"Total space saved: [green]{total_saved // 1024}K[/green]")

    if dry_run:
        return

    now = datetime.now()
    report_name = f"conversion_report_{now.strftime('%Y%m%d_%H%M%S')}.txt"
    try:
        with open(report_name, "w") as f:
            f.write(f"Conversion Report - {now}\n")
            f.write(f"Total: {len(results)}, Success: {success_count}\n\n")
            for r in results:
                status = "OK" if r.success else ("SKIP" if r.skipped else "FAIL")
                f.write(f"  [{status}] {r.input_path}\n")
        console.print(f"Report saved to: [blue]{report_name}[/blue]")
    except OSError:
        console.print("[yellow]Could not save report file[/yellow]")


def _check_and_upgrade(current: str) -> None:
    """Check GitHub for latest release and auto-upgrade if outdated."""
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
            headers={"Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            latest = json.loads(resp.read())["tag_name"].lstrip("v")
    except urllib.error.HTTPError as e:
        if e.code == 403:
            logger.warning("GitHub API rate limit exceeded")
        else:
            logger.debug("Update check HTTP error %s", e.code, exc_info=True)
        return
    except Exception:
        logger.debug("Failed to check for updates", exc_info=True)
        return

    if Version(current) >= Version(latest):
        logger.info("convert-to-mp4 is up to date (v%s)", current)
        return

    logger.info("New version available: v%s (current: v%s)", latest, current)
    console.print(f"[yellow]Upgrading v{current} -> v{latest}...[/yellow]")
    upgrade_commands = [
        ["uv", "tool", "upgrade", "convert-to-mp4"],
        ["uv", "pip", "install", "--upgrade", f"git+https://github.com/{GITHUB_REPO}.git"],
    ]
    for cmd in upgrade_commands:
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            console.print(f"[green]Upgraded to v{latest}. Please re-run your command.[/green]")
            raise typer.Exit(0)
        except typer.Exit:
            raise
        except Exception:
            logger.debug("Upgrade with '%s' failed", " ".join(cmd), exc_info=True)

    logger.warning("All upgrade methods failed")
    console.print(
        "[yellow]Auto-upgrade failed. Run manually:[/yellow]\n  uv tool upgrade convert-to-mp4"
    )


def _validate_quality_range(min_q: int, max_q: int) -> None:
    if min_q > max_q:
        raise typer.BadParameter(
            f"--min-quality ({min_q}) cannot be greater than --max-quality ({max_q})"
        )


def _verbose_callback(value: bool) -> None:
    if value:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")


@app.command()
def _main(
    path: Annotated[
        Path,
        typer.Argument(help="File or directory to convert", exists=True),
    ] = Path("."),
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable debug logging",
            callback=_verbose_callback,
            is_eager=True,
        ),
    ] = False,
    file: Annotated[
        Path | None,
        typer.Option("-f", "--file", help="Convert a specific file", exists=True),
    ] = None,
    directory: Annotated[
        Path | None,
        typer.Option("-d", "--directory", help="Convert all videos in directory", exists=True),
    ] = None,
    recursive: Annotated[
        bool,
        typer.Option("-r", "--recursive", help="Recurse into subdirectories"),
    ] = False,
    jobs: Annotated[
        int,
        typer.Option("-j", "--jobs", help="Parallel conversion jobs", min=1, max=32),
    ] = 1,
    quality: Annotated[
        int | None,
        typer.Option("-q", "--quality", help="Override audio bitrate (64-320)", min=64, max=320),
    ] = None,
    preset: Annotated[
        Preset | None,
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
    current_version = version("convert-to-mp4")
    console.print(f"[dim]convert-to-mp4 v{current_version}[/dim]")
    _check_and_upgrade(current_version)

    if file is not None:
        path = file
    elif directory is not None:
        path = directory
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
        result = convert_single(path, options)
        generate_report([result], dry_run=dry_run)
    else:
        results = convert_directory(path, options)
        generate_report(results, dry_run=dry_run)


def main() -> None:
    app()
