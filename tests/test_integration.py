import subprocess

import pytest

from convert_to_mp4.converter import ConversionOptions, convert_file
from convert_to_mp4.ffmpeg import get_ffmpeg_path, probe


@pytest.fixture
def tiny_video(tmp_path):
    output = tmp_path / "test_input.mkv"
    ffmpeg = get_ffmpeg_path()
    subprocess.run(
        [
            ffmpeg,
            "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=25",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "ac3", "-b:a", "384k",
            "-y",
            str(output),
        ],
        capture_output=True,
        check=True,
    )
    return output


@pytest.mark.integration
class TestProbeIntegration:
    def test_probe_real_video(self, tiny_video):
        result = probe(tiny_video)

        assert result.video_codec == "h264"
        assert result.audio_codec == "ac3"
        assert result.audio_channels >= 1
        assert result.duration > 0

    def test_probe_reports_bitrate(self, tiny_video):
        result = probe(tiny_video)
        assert result.audio_bitrate > 0


@pytest.mark.integration
class TestConvertFileIntegration:
    def test_converts_mkv_to_mp4(self, tiny_video):
        options = ConversionOptions(min_quality=128, max_quality=256)
        result = convert_file(tiny_video, options)

        assert result.success is True
        assert result.output_path.exists()
        assert result.output_path.suffix == ".mp4"
        assert result.output_size > 0

    def test_converted_file_has_aac_audio(self, tiny_video):
        options = ConversionOptions()
        result = convert_file(tiny_video, options)

        probe_result = probe(result.output_path)
        assert probe_result.audio_codec == "aac"
        assert probe_result.audio_channels <= 2

    def test_quality_override(self, tiny_video):
        options = ConversionOptions(quality=128)
        result = convert_file(tiny_video, options)
        assert result.success is True

    def test_dry_run_does_not_create_file(self, tiny_video):
        options = ConversionOptions(dry_run=True)
        result = convert_file(tiny_video, options)

        assert result.skipped is True
        output = tiny_video.with_suffix(".mp4")
        assert not output.exists()
