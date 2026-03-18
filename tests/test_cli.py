# tests/test_cli.py
"""
Tests for life_calendar_cli.py
Uses mocked subprocess calls to avoid system changes.
"""

import os
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def temp_dir(tmp_path):
    """Change CWD to temp dir and restore after."""
    cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(cwd)


class TestEnsureConfig:
    def test_creates_default_config_when_missing(self, temp_dir):
        """_ensure_config should create a JSON config file if none exists."""
        config_path = temp_dir / "life_calendar_config.json"

        import life_calendar_cli
        original_path = life_calendar_cli.CONFIG_PATH
        try:
            life_calendar_cli.CONFIG_PATH = config_path
            life_calendar_cli._ensure_config()
        finally:
            life_calendar_cli.CONFIG_PATH = original_path

        assert config_path.exists()
        data = json.loads(config_path.read_text())
        assert "mode" in data

    def test_does_not_overwrite_existing_config(self, temp_dir):
        """_ensure_config should not overwrite an existing config."""
        config_path = temp_dir / "life_calendar_config.json"
        original = {"mode": "year", "dob": "2000-01-01", "lifespan": 80}
        config_path.write_text(json.dumps(original))

        with patch("life_calendar_cli.CONFIG_PATH", config_path), \
             patch("life_calendar_cli.BASE_DIR", temp_dir):
            from life_calendar_cli import _ensure_config
            _ensure_config()

        data = json.loads(config_path.read_text())
        assert data["mode"] == "year"  # Unchanged


class TestInstallCron:
    @patch("life_calendar_cli.platform.system", return_value="Windows")
    def test_cron_on_windows_exits(self, mock_sys, temp_dir):
        """_install_cron should exit on Windows."""
        from life_calendar_cli import _install_cron
        with pytest.raises(SystemExit):
            _install_cron()

    @patch("life_calendar_cli.platform.system", return_value="Linux")
    def test_cron_missing_wrapper_exits(self, mock_sys, temp_dir):
        """_install_cron should exit if cron_wrapper.sh is missing."""
        with patch("life_calendar_cli.BASE_DIR", temp_dir):
            from life_calendar_cli import _install_cron
            with pytest.raises(SystemExit):
                _install_cron()

    @patch("life_calendar_cli.platform.system", return_value="Linux")
    @patch("life_calendar_cli.subprocess.check_output", return_value=b"")
    @patch("life_calendar_cli.subprocess.run")
    def test_cron_installs_successfully(self, mock_run, mock_check, mock_sys, temp_dir):
        """_install_cron should install a new crontab entry."""
        wrapper = temp_dir / "cron_wrapper.sh"
        wrapper.write_text("#!/bin/bash\npython auto_update.py")

        mock_run.return_value = MagicMock(returncode=0)

        with patch("life_calendar_cli.BASE_DIR", temp_dir):
            from life_calendar_cli import _install_cron
            _install_cron()

        mock_run.assert_called_once()

    @patch("life_calendar_cli.platform.system", return_value="Linux")
    @patch("life_calendar_cli.subprocess.check_output")
    def test_cron_skips_if_already_installed(self, mock_check, mock_sys, temp_dir):
        """_install_cron should skip if the cron line already exists."""
        wrapper = temp_dir / "cron_wrapper.sh"
        wrapper.write_text("#!/bin/bash")

        # Simulate existing crontab that already contains our line
        import shlex
        cron_line = f"1 0 * * * {shlex.quote(str(wrapper))} >> {temp_dir}/cron.log 2>&1"
        mock_check.return_value = cron_line.encode()

        with patch("life_calendar_cli.BASE_DIR", temp_dir):
            from life_calendar_cli import _install_cron
            _install_cron()
            # No subprocess.run call should happen - prints "already installed"


class TestInstallWindowsTask:
    @patch("life_calendar_cli.platform.system", return_value="Linux")
    def test_win_task_on_linux_exits(self, mock_sys, temp_dir):
        """_install_windows_task should exit on non-Windows."""
        from life_calendar_cli import _install_windows_task
        with pytest.raises(SystemExit):
            _install_windows_task()

    @patch("life_calendar_cli.platform.system", return_value="Windows")
    @patch("life_calendar_cli.subprocess.run")
    def test_win_task_creates_successfully(self, mock_run, mock_sys, temp_dir):
        """_install_windows_task should call schtasks."""
        mock_run.return_value = MagicMock(returncode=0)

        with patch("life_calendar_cli.BASE_DIR", temp_dir):
            from life_calendar_cli import _install_windows_task
            _install_windows_task()

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "schtasks" in args[0].lower() or args[0] == "schtasks"


class TestMainEntrypoint:
    def test_run_once_calls_engine(self, temp_dir):
        """--run-once should create engine and call run_auto."""
        # Write a config so the engine can load it
        config_path = temp_dir / "life_calendar_config.json"
        config_path.write_text(json.dumps({
            "mode": "year",
            "dob": "2000-01-01",
            "lifespan": 90,
            "resolution_width": 1920,
            "resolution_height": 1080,
            "config_version": 4,
        }))

        with patch("life_calendar_cli.CONFIG_PATH", config_path), \
             patch("life_calendar_cli.BASE_DIR", temp_dir), \
             patch("wallpaper_engine.WallpaperEngine.run_auto", return_value=True):
            from life_calendar_cli import _run_once
            with pytest.raises(SystemExit) as exc_info:
                _run_once()
            assert exc_info.value.code == 0
