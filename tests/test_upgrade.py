from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock

import click.exceptions
import pytest

from convert_to_mp4.cli import _check_and_upgrade, _should_check_update


@pytest.fixture(autouse=True)
def _allow_upgrade_check(mocker):
    """Override the global autouse mock so these tests can call the real function."""
    mocker.stopall()
    mocker.patch("convert_to_mp4.cli._should_check_update", return_value=True)
    mocker.patch("convert_to_mp4.cli._mark_update_checked")


class TestShouldCheckUpdate:
    def test_returns_true_when_no_cache_file(self, tmp_path, mocker):
        mocker.stopall()
        mocker.patch("convert_to_mp4.cli.CACHE_FILE", tmp_path / "nonexistent")
        assert _should_check_update() is True

    def test_returns_false_when_recently_checked(self, tmp_path, mocker):
        mocker.stopall()
        cache = tmp_path / "last-check"
        cache.touch()
        mocker.patch("convert_to_mp4.cli.CACHE_FILE", cache)
        assert _should_check_update() is False


class TestCheckAndUpgrade:
    def test_skips_when_up_to_date(self, mocker):
        body = json.dumps({"tag_name": "v1.0.0"}).encode()
        resp = MagicMock()
        resp.read.return_value = body
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mocker.patch("urllib.request.urlopen", return_value=resp)
        mock_run = mocker.patch("subprocess.run")

        _check_and_upgrade("1.0.0")

        mock_run.assert_not_called()

    def test_skips_when_local_is_ahead(self, mocker):
        body = json.dumps({"tag_name": "v1.0.0"}).encode()
        resp = MagicMock()
        resp.read.return_value = body
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mocker.patch("urllib.request.urlopen", return_value=resp)
        mock_run = mocker.patch("subprocess.run")

        _check_and_upgrade("2.0.0")

        mock_run.assert_not_called()

    def test_attempts_upgrade_when_behind(self, mocker):
        body = json.dumps({"tag_name": "v2.0.0"}).encode()
        resp = MagicMock()
        resp.read.return_value = body
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mocker.patch("urllib.request.urlopen", return_value=resp)
        mock_run = mocker.patch("subprocess.run")

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            _check_and_upgrade("1.0.0")

        mock_run.assert_called_once()
        assert "upgrade" in mock_run.call_args[0][0]

    def test_falls_back_on_first_command_failure(self, mocker):
        body = json.dumps({"tag_name": "v2.0.0"}).encode()
        resp = MagicMock()
        resp.read.return_value = body
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mocker.patch("urllib.request.urlopen", return_value=resp)
        import subprocess

        mock_run = mocker.patch(
            "subprocess.run",
            side_effect=[subprocess.CalledProcessError(1, "uv"), None],
        )

        with pytest.raises((SystemExit, click.exceptions.Exit)):
            _check_and_upgrade("1.0.0")

        assert mock_run.call_count == 2

    def test_shows_manual_message_when_all_fail(self, mocker, capsys):
        body = json.dumps({"tag_name": "v2.0.0"}).encode()
        resp = MagicMock()
        resp.read.return_value = body
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mocker.patch("urllib.request.urlopen", return_value=resp)
        import subprocess

        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "uv"),
        )

        _check_and_upgrade("1.0.0")

    def test_returns_silently_on_network_failure(self, mocker):
        mocker.patch("urllib.request.urlopen", side_effect=OSError("no network"))
        mock_run = mocker.patch("subprocess.run")

        _check_and_upgrade("1.0.0")

        mock_run.assert_not_called()

    def test_returns_silently_on_rate_limit(self, mocker):
        mocker.patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError("url", 403, "rate limited", {}, None),
        )
        mock_run = mocker.patch("subprocess.run")

        _check_and_upgrade("1.0.0")

        mock_run.assert_not_called()
