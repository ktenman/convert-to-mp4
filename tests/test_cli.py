from typer.testing import CliRunner

from convert_to_mp4.cli import app

runner = CliRunner()


class TestHelpOutput:
    def test_help_shows_usage(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "convert" in result.output.lower() or "Usage" in result.output


class TestPresetOption:
    def test_preset_mobile(self, mocker):
        mock_convert_dir = mocker.patch(
            "convert_to_mp4.cli.convert_directory", return_value=[]
        )
        mocker.patch("convert_to_mp4.cli.generate_report")
        result = runner.invoke(app, ["--preset", "mobile", "--dry-run", "."])
        assert result.exit_code == 0
        call_args = mock_convert_dir.call_args
        options = call_args[0][1] if len(call_args[0]) > 1 else call_args.kwargs.get("options")
        assert options.min_quality == 128
        assert options.max_quality == 160

    def test_invalid_preset_rejected(self):
        result = runner.invoke(app, ["--preset", "invalid"])
        assert result.exit_code != 0


class TestQualityOption:
    def test_quality_override(self, mocker):
        mock_convert_dir = mocker.patch(
            "convert_to_mp4.cli.convert_directory", return_value=[]
        )
        mocker.patch("convert_to_mp4.cli.generate_report")
        result = runner.invoke(app, ["-q", "192", "--dry-run", "."])
        assert result.exit_code == 0
        call_args = mock_convert_dir.call_args
        options = call_args[0][1] if len(call_args[0]) > 1 else call_args.kwargs.get("options")
        assert options.quality == 192

    def test_quality_out_of_range_rejected(self):
        result = runner.invoke(app, ["-q", "999", "."])
        assert result.exit_code != 0


class TestFileAndDirectoryOptions:
    def test_f_flag_converts_specific_file(self, tmp_path, mocker):
        video = tmp_path / "test.mkv"
        video.write_bytes(b"\x00" * 1024)

        mock_convert_file = mocker.patch(
            "convert_to_mp4.cli.convert_file",
            return_value=mocker.MagicMock(success=True, skipped=False),
        )
        mocker.patch("convert_to_mp4.cli.generate_report")

        result = runner.invoke(app, ["-f", str(video)])
        assert result.exit_code == 0
        mock_convert_file.assert_called_once()

    def test_d_flag_converts_directory(self, tmp_path, mocker):
        mock_convert_dir = mocker.patch(
            "convert_to_mp4.cli.convert_directory", return_value=[]
        )
        mocker.patch("convert_to_mp4.cli.generate_report")

        result = runner.invoke(app, ["-d", str(tmp_path)])
        assert result.exit_code == 0
        mock_convert_dir.assert_called_once()


class TestMinMaxQualityValidation:
    def test_min_greater_than_max_rejected(self, mocker):
        mocker.patch("convert_to_mp4.cli.convert_directory", return_value=[])
        mocker.patch("convert_to_mp4.cli.generate_report")
        result = runner.invoke(app, ["--min-quality", "300", "--max-quality", "100", "."])
        assert result.exit_code != 0
