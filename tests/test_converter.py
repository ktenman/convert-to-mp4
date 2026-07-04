from pathlib import Path
from unittest.mock import MagicMock

import pytest

from convert_to_mp4.audio import LoudnessStats
from convert_to_mp4.converter import (
    ConversionOptions,
    ConversionResult,
    check_disk_space,
    convert_directory,
    convert_file,
    find_video_files,
)
from convert_to_mp4.ffmpeg import ProbeResult


@pytest.fixture
def default_options():
    return ConversionOptions()


@pytest.fixture
def compatible_probe():
    return ProbeResult(
        video_codec="h264",
        audio_codec="aac",
        audio_bitrate=192000,
        audio_channels=2,
        duration=60.0,
    )


@pytest.fixture
def incompatible_probe():
    return ProbeResult(
        video_codec="h264",
        audio_codec="ac3",
        audio_bitrate=384000,
        audio_channels=6,
        duration=60.0,
    )


class TestConvertFile:
    @pytest.fixture(autouse=True)
    def _no_loudness_measurement(self, mocker):
        mocker.patch("convert_to_mp4.converter.measure_loudness", return_value=None)

    def test_skips_already_compatible_mp4(
        self, tmp_path, mocker, compatible_probe, default_options
    ):
        video = tmp_path / "test.mp4"
        video.write_bytes(b"\x00" * 1024)

        mocker.patch("convert_to_mp4.converter.probe", return_value=compatible_probe)
        mock_run = mocker.patch("convert_to_mp4.converter.run_conversion")

        result = convert_file(video, default_options)

        assert result.skipped is True
        mock_run.assert_not_called()

    def test_converts_incompatible_audio(
        self, tmp_path, mocker, incompatible_probe, default_options
    ):
        video = tmp_path / "test.mkv"
        video.write_bytes(b"\x00" * 1024)

        mocker.patch("convert_to_mp4.converter.probe", return_value=incompatible_probe)
        mock_run = mocker.patch("convert_to_mp4.converter.run_conversion", return_value=True)
        mocker.patch("convert_to_mp4.converter.check_disk_space", return_value=True)
        mocker.patch("pathlib.Path.stat", return_value=MagicMock(st_size=800))

        result = convert_file(video, default_options)

        assert result.success is True
        mock_run.assert_called_once()
        call_params = mock_run.call_args
        params = call_params.kwargs.get("params") or call_params[0][2]
        assert "-c:a" in params
        assert "aac" in params

    def test_dry_run_does_not_call_ffmpeg(self, tmp_path, mocker, incompatible_probe):
        video = tmp_path / "test.mkv"
        video.write_bytes(b"\x00" * 1024)

        mocker.patch("convert_to_mp4.converter.probe", return_value=incompatible_probe)
        mock_run = mocker.patch("convert_to_mp4.converter.run_conversion")

        options = ConversionOptions(dry_run=True)
        result = convert_file(video, options)

        assert result.skipped is True
        assert result.skip_reason == "dry run"
        mock_run.assert_not_called()

    def test_error_recovery_retries_on_failure(
        self, tmp_path, mocker, incompatible_probe, default_options
    ):
        video = tmp_path / "test.mkv"
        video.write_bytes(b"\x00" * 1024)

        mocker.patch("convert_to_mp4.converter.probe", return_value=incompatible_probe)
        mocker.patch("convert_to_mp4.converter.check_disk_space", return_value=True)
        mock_run = mocker.patch(
            "convert_to_mp4.converter.run_conversion",
            side_effect=[False, False, True],
        )
        mocker.patch("pathlib.Path.stat", return_value=MagicMock(st_size=800))
        mocker.patch("pathlib.Path.exists", return_value=False)

        result = convert_file(video, default_options)

        assert result.success is True
        assert mock_run.call_count == 3

    def test_all_attempts_fail_returns_failure(
        self, tmp_path, mocker, incompatible_probe, default_options
    ):
        video = tmp_path / "test.mkv"
        video.write_bytes(b"\x00" * 1024)

        mocker.patch("convert_to_mp4.converter.probe", return_value=incompatible_probe)
        mocker.patch("convert_to_mp4.converter.check_disk_space", return_value=True)
        mock_run = mocker.patch("convert_to_mp4.converter.run_conversion", return_value=False)
        mocker.patch("pathlib.Path.exists", return_value=True)
        mocker.patch("pathlib.Path.unlink")

        result = convert_file(video, default_options)

        assert result.success is False
        assert mock_run.call_count == 3

    def test_mp4_with_incompatible_audio_uses_temp_file(
        self, tmp_path, mocker, incompatible_probe, default_options
    ):
        video = tmp_path / "test.mp4"
        video.write_bytes(b"\x00" * 1024)

        mocker.patch("convert_to_mp4.converter.probe", return_value=incompatible_probe)
        mock_run = mocker.patch("convert_to_mp4.converter.run_conversion", return_value=True)
        mocker.patch("convert_to_mp4.converter.check_disk_space", return_value=True)
        mocker.patch("pathlib.Path.stat", return_value=MagicMock(st_size=800))
        mocker.patch("pathlib.Path.replace")

        result = convert_file(video, default_options)

        assert result.success is True
        call_args = mock_run.call_args
        output_used = call_args.kwargs.get("output_path") or call_args[0][1]
        assert ".converting." in output_used.name

    def test_mp4_failure_does_not_delete_original(
        self, tmp_path, mocker, incompatible_probe, default_options
    ):
        video = tmp_path / "test.mp4"
        video.write_bytes(b"\x00" * 1024)

        mocker.patch("convert_to_mp4.converter.probe", return_value=incompatible_probe)
        mocker.patch("convert_to_mp4.converter.run_conversion", return_value=False)
        mocker.patch("convert_to_mp4.converter.check_disk_space", return_value=True)
        mocker.patch("pathlib.Path.unlink")

        result = convert_file(video, default_options)

        assert result.success is False
        assert video.exists()


class TestLoudnessNormalization:
    @pytest.fixture
    def loudness_stats(self):
        return LoudnessStats(
            input_i=-27.2,
            input_tp=-4.9,
            input_lra=16.1,
            input_thresh=-38.1,
            target_offset=0.4,
        )

    def _convert(self, tmp_path, mocker, probe_result, options):
        video = tmp_path / "test.mkv"
        video.write_bytes(b"\x00" * 1024)

        mocker.patch("convert_to_mp4.converter.probe", return_value=probe_result)
        mocker.patch("convert_to_mp4.converter.check_disk_space", return_value=True)
        mock_run = mocker.patch("convert_to_mp4.converter.run_conversion", return_value=True)
        mocker.patch("pathlib.Path.stat", return_value=MagicMock(st_size=800))

        convert_file(video, options)

        call_args = mock_run.call_args
        return call_args.kwargs.get("params") or call_args[0][2]

    def test_reencode_applies_loudnorm_filter(
        self, tmp_path, mocker, incompatible_probe, default_options, loudness_stats
    ):
        mock_measure = mocker.patch(
            "convert_to_mp4.converter.measure_loudness", return_value=loudness_stats
        )

        params = self._convert(tmp_path, mocker, incompatible_probe, default_options)

        mock_measure.assert_called_once()
        filter_str = params[params.index("-af") + 1]
        assert "loudnorm" in filter_str
        assert "measured_I=-27.2" in filter_str
        assert "linear=true" in filter_str
        assert params[params.index("-ar") + 1] == "48000"
        assert "-ac" not in params

    def test_failed_measurement_falls_back_to_plain_downmix(
        self, tmp_path, mocker, incompatible_probe, default_options
    ):
        mocker.patch("convert_to_mp4.converter.measure_loudness", return_value=None)

        params = self._convert(tmp_path, mocker, incompatible_probe, default_options)

        assert "-af" not in params
        assert params[params.index("-ac") + 1] == "2"

    def test_no_normalize_skips_measurement(self, tmp_path, mocker, incompatible_probe):
        mock_measure = mocker.patch("convert_to_mp4.converter.measure_loudness")

        params = self._convert(
            tmp_path, mocker, incompatible_probe, ConversionOptions(normalize=False)
        )

        mock_measure.assert_not_called()
        assert "-af" not in params

    def test_copied_audio_skips_measurement(self, tmp_path, mocker, compatible_probe):
        mock_measure = mocker.patch("convert_to_mp4.converter.measure_loudness")

        params = self._convert(tmp_path, mocker, compatible_probe, ConversionOptions())

        mock_measure.assert_not_called()
        assert params[params.index("-c:a") + 1] == "copy"


class TestConvertDirectory:
    @pytest.fixture(autouse=True)
    def _quiet_console(self, mocker):
        from io import StringIO

        from rich.console import Console as RichConsole

        quiet = RichConsole(file=StringIO(), no_color=True)
        mocker.patch("convert_to_mp4.converter.console", quiet)

    def test_returns_empty_for_no_video_files(self, tmp_path):
        (tmp_path / "readme.txt").touch()

        results = convert_directory(tmp_path, ConversionOptions())
        assert results == []

    def test_converts_all_video_files(self, tmp_path, mocker):
        (tmp_path / "a.mkv").write_bytes(b"\x00" * 1024)
        (tmp_path / "b.avi").write_bytes(b"\x00" * 1024)

        mock_convert = mocker.patch(
            "convert_to_mp4.converter.convert_file",
            return_value=ConversionResult(
                input_path=tmp_path / "a.mkv",
                output_path=tmp_path / "a.mp4",
                success=True,
            ),
        )

        results = convert_directory(tmp_path, ConversionOptions())

        assert len(results) == 2
        assert mock_convert.call_count == 2

    def test_parallel_converts_all_files(self, tmp_path, mocker):
        (tmp_path / "a.mkv").write_bytes(b"\x00" * 1024)
        (tmp_path / "b.mkv").write_bytes(b"\x00" * 1024)

        mocker.patch(
            "convert_to_mp4.converter.convert_file",
            return_value=ConversionResult(
                input_path=tmp_path / "a.mkv",
                output_path=tmp_path / "a.mp4",
                success=True,
            ),
        )

        options = ConversionOptions(jobs=2)
        results = convert_directory(tmp_path, options)

        assert len(results) == 2


class TestFindVideoFiles:
    def test_finds_video_files_in_directory(self, tmp_path):
        (tmp_path / "video.mkv").touch()
        (tmp_path / "video.avi").touch()
        (tmp_path / "readme.txt").touch()

        files = find_video_files(tmp_path, recursive=False)
        extensions = {f.suffix for f in files}

        assert len(files) == 2
        assert extensions == {".mkv", ".avi"}

    def test_recursive_finds_nested_files(self, tmp_path):
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "top.mkv").touch()
        (subdir / "nested.mp4").touch()

        files = find_video_files(tmp_path, recursive=True)
        assert len(files) == 2

    def test_non_recursive_ignores_nested(self, tmp_path):
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "top.mkv").touch()
        (subdir / "nested.mp4").touch()

        files = find_video_files(tmp_path, recursive=False)
        assert len(files) == 1


class TestCheckDiskSpace:
    def test_returns_true_with_enough_space(self, mocker):
        mocker.patch("shutil.disk_usage", return_value=MagicMock(free=10_000_000))
        assert check_disk_space(Path("/fake"), file_size=1_000_000) is True

    def test_returns_false_with_insufficient_space(self, mocker):
        mocker.patch("shutil.disk_usage", return_value=MagicMock(free=100))
        assert check_disk_space(Path("/fake"), file_size=1_000_000) is False
