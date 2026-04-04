from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Preset(StrEnum):
    TV = "tv"
    MOBILE = "mobile"
    ARCHIVE = "archive"
    QUICK = "quick"


@dataclass(frozen=True)
class PresetConfig:
    min_quality: int
    max_quality: int
    description: str


_PRESET_CONFIGS: dict[Preset, PresetConfig] = {
    Preset.TV: PresetConfig(192, 256, "High quality for smart TVs"),
    Preset.MOBILE: PresetConfig(128, 160, "Smaller files for phones"),
    Preset.ARCHIVE: PresetConfig(256, 320, "Maximum quality preservation"),
    Preset.QUICK: PresetConfig(128, 192, "Fastest conversion"),
}


def get_preset_config(preset: Preset) -> PresetConfig:
    return _PRESET_CONFIGS[preset]
