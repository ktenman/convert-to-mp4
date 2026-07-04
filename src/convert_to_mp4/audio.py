from __future__ import annotations

from dataclasses import dataclass

STANDARD_BITRATES = (128, 160, 192, 224, 256, 320)
DEFAULT_BITRATE = 192

LOUDNESS_TARGET_I = -16.0
LOUDNESS_TARGET_TP = -1.5
LOUDNESS_TARGET_LRA = 11.0


@dataclass(frozen=True)
class AudioInfo:
    codec: str
    channels: int
    bitrate: int


@dataclass(frozen=True)
class LoudnessStats:
    input_i: float
    input_tp: float
    input_lra: float
    input_thresh: float
    target_offset: float


def build_loudnorm_filter(stats: LoudnessStats | None = None) -> str:
    base = (
        "aformat=channel_layouts=stereo,"
        f"loudnorm=I={LOUDNESS_TARGET_I:g}:TP={LOUDNESS_TARGET_TP:g}:LRA={LOUDNESS_TARGET_LRA:g}"
    )
    if stats is None:
        return f"{base}:print_format=json"
    return (
        f"{base}:measured_I={stats.input_i:g}:measured_TP={stats.input_tp:g}"
        f":measured_LRA={stats.input_lra:g}:measured_thresh={stats.input_thresh:g}"
        f":offset={stats.target_offset:g}:linear=true"
    )


def calculate_optimal_bitrate(
    source_bitrate: int | None,
    source_codec: str,
    min_quality: int,
    max_quality: int,
) -> int:
    if not source_bitrate:
        return DEFAULT_BITRATE

    if source_bitrate > 10000:
        source_bitrate = source_bitrate // 1000

    match source_codec:
        case "ac3" | "eac3":
            target = source_bitrate * 2 // 3
        case "mp3":
            target = source_bitrate * 7 // 10
        case "aac":
            target = source_bitrate
        case _:
            target = source_bitrate * 3 // 4

    closest = target
    for bitrate in STANDARD_BITRATES:
        if bitrate >= target:
            closest = bitrate
            break
    else:
        closest = STANDARD_BITRATES[-1]

    return max(min_quality, min(closest, max_quality))


def should_reencode(audio_info: AudioInfo, force_audio: bool) -> bool:
    if force_audio:
        return True
    if audio_info.codec != "aac":
        return True
    return audio_info.channels > 2
