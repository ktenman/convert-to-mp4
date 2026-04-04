import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from convert_to_mp4.ffmpeg import (
    ProbeResult,
    get_ffmpeg_path,
    get_ffprobe_path,
    probe,
    run_conversion,
)

SAMPLE_FFPROBE_OUTPUT = json.dumps(
    {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
            },
            {
                "codec_type": "audio",
                "codec_name": "ac3",
                "bit_rate": "384000",
                "channels": 6,
            },
        ],
        "format": {
            "duration": "3600.5",
        },
    }
)

SAMPLE_FFPROBE_NO_AUDIO_BITRATE = json.dumps(
    {
        "streams": [
            {"codec_type": "video", "codec_name": "h264"},
            {"codec_type": "audio", "codec_name": "aac", "channels": 2},
        ],
        "format": {"duration": "120.0", "bit_rate": "5000000"},
    }
)


class TestGetFfmpegPath:
    def test_prefers_imageio_ffmpeg(self, mocker):
        mocker.patch("imageio_ffmpeg.get_ffmpeg_exe", return_value="/bundled/ffmpeg")
        assert get_ffmpeg_path() == "/bundled/ffmpeg"

    def test_falls_back_to_system(self, mocker):
        mocker.patch("imageio_ffmpeg.get_ffmpeg_exe", side_effect=Exception("no bundle"))
        mocker.patch("shutil.which", return_value="/usr/bin/ffmpeg")
        assert get_ffmpeg_path() == "/usr/bin/ffmpeg"

    def test_raises_if_not_found(self, mocker):
        mocker.patch("imageio_ffmpeg.get_ffmpeg_exe", side_effect=Exception("no bundle"))
        mocker.patch("shutil.which", return_value=None)
        with pytest.raises(RuntimeError, match="ffmpeg not found"):
            get_ffmpeg_path()


class TestGetFfprobePath:
    def test_finds_ffprobe_next_to_bundled_ffmpeg(self, mocker, tmp_path):
        ffprobe_path = tmp_path / "ffprobe"
        ffprobe_path.touch()
        ffprobe_path.chmod(0o755)
        mocker.patch(
            "convert_to_mp4.ffmpeg.get_ffmpeg_path",
            return_value=str(tmp_path / "ffmpeg"),
        )
        assert get_ffprobe_path() == str(ffprobe_path)

    def test_falls_back_to_system_ffprobe(self, mocker, tmp_path):
        mocker.patch(
            "convert_to_mp4.ffmpeg.get_ffmpeg_path",
            return_value=str(tmp_path / "ffmpeg"),
        )
        mocker.patch("shutil.which", return_value="/usr/bin/ffprobe")
        assert get_ffprobe_path() == "/usr/bin/ffprobe"

    def test_raises_if_not_found(self, mocker, tmp_path):
        mocker.patch(
            "convert_to_mp4.ffmpeg.get_ffmpeg_path",
            return_value=str(tmp_path / "ffmpeg"),
        )
        mocker.patch("shutil.which", return_value=None)
        with pytest.raises(RuntimeError, match="ffprobe not found"):
            get_ffprobe_path()


class TestProbe:
    def test_parses_complete_output(self, mocker):
        mocker.patch("convert_to_mp4.ffmpeg.get_ffprobe_path", return_value="/usr/bin/ffprobe")
        mocker.patch(
            "subprocess.run",
            return_value=MagicMock(stdout=SAMPLE_FFPROBE_OUTPUT, returncode=0),
        )
        result = probe(Path("/fake/video.mkv"))

        assert result.video_codec == "h264"
        assert result.audio_codec == "ac3"
        assert result.audio_bitrate == 384000
        assert result.audio_channels == 6
        assert result.duration == 3600.5

    def test_handles_missing_audio_bitrate(self, mocker):
        mocker.patch("convert_to_mp4.ffmpeg.get_ffprobe_path", return_value="/usr/bin/ffprobe")
        mocker.patch(
            "subprocess.run",
            return_value=MagicMock(stdout=SAMPLE_FFPROBE_NO_AUDIO_BITRATE, returncode=0),
        )
        result = probe(Path("/fake/video.mkv"))

        assert result.audio_codec == "aac"
        assert result.audio_bitrate == 0
        assert result.audio_channels == 2

    def test_raises_on_ffprobe_failure(self, mocker):
        mocker.patch("convert_to_mp4.ffmpeg.get_ffprobe_path", return_value="/usr/bin/ffprobe")
        mocker.patch(
            "subprocess.run",
            return_value=MagicMock(stdout="", returncode=1, stderr="error"),
        )
        with pytest.raises(RuntimeError, match="ffprobe failed"):
            probe(Path("/fake/video.mkv"))


class TestRunConversion:
    def test_builds_correct_command(self, mocker):
        mocker.patch("convert_to_mp4.ffmpeg.get_ffmpeg_path", return_value="/usr/bin/ffmpeg")
        mock_popen = MagicMock()
        mock_popen.stdout.readline.side_effect = [b"progress=end\n", b""]
        mock_popen.wait.return_value = 0
        mocker.patch("subprocess.Popen", return_value=mock_popen)

        result = run_conversion(
            input_path=Path("/fake/input.mkv"),
            output_path=Path("/fake/output.mp4"),
            params=["-c:v", "copy", "-c:a", "aac", "-b:a", "192k"],
            duration=60.0,
            on_progress=None,
        )

        assert result is True
        popen_call = subprocess.Popen.call_args
        cmd = popen_call[0][0]
        assert cmd[0] == "/usr/bin/ffmpeg"
        assert "-i" in cmd
        assert "/fake/input.mkv" in cmd
        assert "/fake/output.mp4" in cmd

    def test_calls_progress_callback(self, mocker):
        mocker.patch("convert_to_mp4.ffmpeg.get_ffmpeg_path", return_value="/usr/bin/ffmpeg")

        progress_lines = [
            b"out_time_us=30000000\n",
            b"progress=continue\n",
            b"out_time_us=60000000\n",
            b"progress=end\n",
            b"",
        ]
        mock_popen = MagicMock()
        mock_popen.stdout.readline.side_effect = progress_lines
        mock_popen.wait.return_value = 0
        mocker.patch("subprocess.Popen", return_value=mock_popen)

        callback = MagicMock()
        run_conversion(
            input_path=Path("/fake/input.mkv"),
            output_path=Path("/fake/output.mp4"),
            params=["-c:v", "copy"],
            duration=60.0,
            on_progress=callback,
        )

        assert callback.call_count >= 1

    def test_returns_false_on_failure(self, mocker):
        mocker.patch("convert_to_mp4.ffmpeg.get_ffmpeg_path", return_value="/usr/bin/ffmpeg")
        mock_popen = MagicMock()
        mock_popen.stdout.readline.side_effect = [b"progress=end\n", b""]
        mock_popen.wait.return_value = 1
        mocker.patch("subprocess.Popen", return_value=mock_popen)

        result = run_conversion(
            input_path=Path("/fake/input.mkv"),
            output_path=Path("/fake/output.mp4"),
            params=["-c:v", "copy"],
            duration=60.0,
            on_progress=None,
        )

        assert result is False
