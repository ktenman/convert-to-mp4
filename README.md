# convert-to-mp4

Smart video converter with automatic audio quality detection.

Converts video files to browser-compatible MP4 with intelligent audio bitrate selection, progress tracking, error recovery, and presets.

## Installation

```bash
uv tool install git+https://github.com/ktenman/convert-to-mp4
```

## Usage

```bash
# Convert all videos in current directory
convert-to-mp4

# Convert a specific file
convert-to-mp4 video.mkv

# Convert with a preset
convert-to-mp4 --preset mobile /path/to/videos

# Parallel conversion
convert-to-mp4 -j 4 .

# Dry run
convert-to-mp4 --dry-run .
```

## Options

| Option | Description |
|---|---|
| `PATH` | File or directory (default: `.`) |
| `-r, --recursive` | Recurse into subdirectories |
| `-j, --jobs` | Parallel jobs (default: 1) |
| `-q, --quality` | Override audio bitrate (64-320) |
| `--preset` | `tv`, `mobile`, `archive`, `quick` |
| `--min-quality` | Minimum audio bitrate (default: 128) |
| `--max-quality` | Maximum audio bitrate (default: 256) |
| `--force-audio` | Re-encode even if already AAC |
| `--dry-run` | Show what would happen |
