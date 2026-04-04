"""Shared test fixtures for convert-to-mp4."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_probe(mocker):
    """Return a factory that creates a mock probe function returning a ProbeResult."""
    from convert_to_mp4.ffmpeg import ProbeResult

    def _factory(
        video_codec: str = "h264",
        audio_codec: str = "aac",
        audio_bitrate: int = 192,
        audio_channels: int = 2,
        duration: float = 60.0,
    ) -> MagicMock:
        result = ProbeResult(
            video_codec=video_codec,
            audio_codec=audio_codec,
            audio_bitrate=audio_bitrate,
            audio_channels=audio_channels,
            duration=duration,
        )
        mock = mocker.patch("convert_to_mp4.ffmpeg.probe", return_value=result)
        return mock

    return _factory


@pytest.fixture
def tmp_video(tmp_path):
    """Create a fake video file path for unit tests (no real video data)."""
    video = tmp_path / "test_video.mkv"
    video.write_bytes(b"\x00" * 1024)
    return video
