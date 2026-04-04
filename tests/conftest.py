from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clear_ffmpeg_cache():
    yield
    from convert_to_mp4.ffmpeg import get_ffmpeg_path, get_ffprobe_path

    get_ffmpeg_path.cache_clear()
    get_ffprobe_path.cache_clear()


@pytest.fixture(autouse=True)
def _no_upgrade_check(mocker):
    mocker.patch("convert_to_mp4.cli._check_and_upgrade")


@pytest.fixture
def tmp_video(tmp_path):
    video = tmp_path / "test_video.mkv"
    video.write_bytes(b"\x00" * 1024)
    return video
