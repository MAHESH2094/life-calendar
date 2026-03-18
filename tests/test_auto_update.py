# tests/test_auto_update.py
"""
Tests for auto_update.py
Covers the needs_update/mark_updated guard and main() flow.
"""

import os
import sys
import json
import pytest
from pathlib import Path
from datetime import date
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def temp_dir(tmp_path):
    """Change CWD to temp dir and restore after."""
    cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(cwd)


def _write_config(tmp_path):
    """Write a minimal valid config for auto_update to use."""
    cfg = {
        "mode": "year",
        "dob": "2000-01-01",
        "lifespan": 90,
        "resolution_width": 1920,
        "resolution_height": 1080,
        "config_version": 4,
        "automation": {
            "startup_enabled": True,
            "wallpaper_refresh_enabled": True,
        },
    }
    cfg_path = tmp_path / "life_calendar_config.json"
    cfg_path.write_text(json.dumps(cfg))
    return cfg_path


class TestNeedsUpdate:
    def test_first_run_needs_update(self, temp_dir):
        """First run (no timestamp file) should need an update."""
        with patch("auto_update.BASE_DIR", temp_dir):
            from auto_update import needs_update
            assert needs_update() is True

    def test_after_mark_updated_no_update(self, temp_dir):
        """After mark_updated(), needs_update() should return False."""
        with patch("auto_update.BASE_DIR", temp_dir):
            from auto_update import needs_update, mark_updated
            mark_updated()
            assert needs_update() is False

    def test_stale_timestamp_needs_update(self, temp_dir):
        """If timestamp file has yesterday's date, update is needed."""
        ts_file = temp_dir / ".last_update_date"
        ts_file.write_text("2020-01-01")

        with patch("auto_update.BASE_DIR", temp_dir):
            from auto_update import needs_update
            assert needs_update() is True

    def test_today_timestamp_skips(self, temp_dir):
        """If timestamp has today's date, no update needed."""
        ts_file = temp_dir / ".last_update_date"
        ts_file.write_text(str(date.today()))

        with patch("auto_update.BASE_DIR", temp_dir):
            from auto_update import needs_update
            assert needs_update() is False


class TestMarkUpdated:
    def test_creates_timestamp_file(self, temp_dir):
        """mark_updated() should create the timestamp file."""
        with patch("auto_update.BASE_DIR", temp_dir):
            from auto_update import mark_updated
            mark_updated()

        ts_file = temp_dir / ".last_update_date"
        assert ts_file.exists()
        assert ts_file.read_text().strip() == str(date.today())


class TestMain:
    def test_skips_if_already_updated(self, temp_dir):
        """main() should return 0 and skip if already updated today."""
        ts_file = temp_dir / ".last_update_date"
        ts_file.write_text(str(date.today()))

        with patch("auto_update.BASE_DIR", temp_dir), \
             patch("auto_update.get_base_dir", return_value=temp_dir):
            from auto_update import main
            result = main()
            assert result == 0

    def test_missing_config_returns_1(self, temp_dir):
        """main() should return 1 if config file is missing."""
        with patch("auto_update.BASE_DIR", temp_dir), \
             patch("auto_update.get_base_dir", return_value=temp_dir):
            from auto_update import main
            result = main()
            assert result == 1

    def test_successful_update(self, temp_dir):
        """main() should generate wallpaper and return 0 on success."""
        _write_config(temp_dir)

        # Copy wallpaper_engine.py to temp_dir so auto_update can import it
        engine_src = Path(__file__).parent.parent / "wallpaper_engine.py"
        engine_dst = temp_dir / "wallpaper_engine.py"
        if engine_src.exists():
            import shutil
            shutil.copy(engine_src, engine_dst)

        with patch("auto_update.BASE_DIR", temp_dir), \
             patch("auto_update.get_base_dir", return_value=temp_dir):
            # Mock the engine's run_auto to avoid real wallpaper setting
            with patch("wallpaper_engine.WallpaperEngine.run_auto", return_value=True):
                from auto_update import main
                result = main()
                assert result == 0

            # Timestamp should be written
            ts_file = temp_dir / ".last_update_date"
            assert ts_file.exists()
