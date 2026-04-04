from __future__ import annotations

from dataclasses import dataclass

STANDARD_BITRATES = (128, 160, 192, 224, 256, 320)
DEFAULT_BITRATE = 192


@dataclass(frozen=True)
class AudioInfo:
    codec: str
    channels: int
    bitrate: int


def calculate_optimal_bitrate(
    source_bitrate: int | None,
    source_codec: str,
    min_quality: int,
    max_quality: int,
) -> int:
    if not source_bitrate:
        return DEFAULT_BITRATE

    if source_bitrate > 1000:
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
    if audio_info.channels > 2:
        return True
    return False
