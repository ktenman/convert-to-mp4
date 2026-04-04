from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _clear_ffmpeg_cache():
    yield
    from convert_to_mp4.ffmpeg import get_ffmpeg_path, get_ffprobe_path

    get_ffmpeg_path.cache_clear()
    get_ffprobe_path.cache_clear()


@pytest.fixture
def mock_probe(mocker):
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
    video = tmp_path / "test_video.mkv"
    video.write_bytes(b"\x00" * 1024)
    return video
