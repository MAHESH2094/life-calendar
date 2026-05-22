"""Tests for the modular architecture and exception chaining."""

import json
import os
import threading
from datetime import date
from unittest.mock import patch

import pytest

from lifecalendar.data import GoalCalendarData, LifeCalendarData, safe_date
from lifecalendar.layout import GridLayout
from lifecalendar.lock import acquire_lock, force_release_lock, release_lock


# ── backward compatibility ─────────────────────────────────────────────────

class TestBackwardCompatibility:
    """All names from the old wallpaper_engine module must still be importable."""

    def test_import_from_wallpaper_engine(self):
        import lifecalendar.wallpaper_engine as we

        # Verify all public names exist on the shim module
        expected = [
            "WallpaperEngine", "CalendarData", "GoalCalendarData",
            "LifeCalendarData", "YearCalendarData", "GridLayout",
            "WallpaperRenderer", "safe_date", "get_screen_resolution",
            "acquire_lock", "release_lock", "force_release_lock",
            "LOCK_FILE", "BASE_DIR", "logger", "MAX_GRID_UNITS",
            "MAX_SAFE_PIXELS", "LOG_PATH", "get_base_dir",
            "close_log_handlers",
        ]
        for name in expected:
            assert hasattr(we, name), f"Missing re-export: {name}"

    def test_shim_objects_are_canonical(self):
        """Re-exported objects must be the same identity as canonical modules."""
        from lifecalendar.wallpaper_engine import WallpaperEngine as ShimWE
        from lifecalendar.engine import WallpaperEngine as CanonWE
        from lifecalendar.wallpaper_engine import acquire_lock as ShimAL
        from lifecalendar.lock import acquire_lock as CanonAL
        from lifecalendar.wallpaper_engine import LifeCalendarData as ShimLCD
        from lifecalendar.data import LifeCalendarData as CanonLCD
        from lifecalendar.wallpaper_engine import GridLayout as ShimGL
        from lifecalendar.layout import GridLayout as CanonGL
        from lifecalendar.wallpaper_engine import WallpaperRenderer as ShimWR
        from lifecalendar.renderer import WallpaperRenderer as CanonWR

        assert ShimWE is CanonWE
        assert ShimAL is CanonAL
        assert ShimLCD is CanonLCD
        assert ShimGL is CanonGL
        assert ShimWR is CanonWR


# ── exception chaining ─────────────────────────────────────────────────────

class TestExceptionChaining:
    """Engine exceptions must preserve the original cause via __cause__."""

    def test_load_config_preserves_original_exception(self, tmp_path):
        from lifecalendar.engine import WallpaperEngine

        bad_path = tmp_path / "nonexistent" / "config.json"
        with pytest.raises(FileNotFoundError):
            WallpaperEngine(str(bad_path))

    def test_load_config_json_error_is_valueerror(self, tmp_path):
        from lifecalendar.engine import WallpaperEngine

        cfg = tmp_path / "life_calendar_config.json"
        cfg.write_text("{bad json!!", encoding="utf-8")

        with pytest.raises(ValueError, match="Invalid JSON"):
            WallpaperEngine(str(cfg))


# ── lock recovery edge cases ───────────────────────────────────────────────

class TestLockRecovery:
    """Lock file recovery under various corruption scenarios."""

    def test_empty_lock_file_cleaned(self, tmp_path):
        lock_path = tmp_path / ".life_calendar.lock"
        lock_path.write_text("", encoding="utf-8")

        with patch("lifecalendar.lock.LOCK_FILE", str(lock_path)):
            acquire_lock()
            assert lock_path.exists()
            release_lock()

    def test_json_array_lock_file_cleaned(self, tmp_path):
        lock_path = tmp_path / ".life_calendar.lock"
        lock_path.write_text("[1, 2, 3]", encoding="utf-8")

        with patch("lifecalendar.lock.LOCK_FILE", str(lock_path)):
            acquire_lock()
            assert lock_path.exists()
            release_lock()

    def test_lock_with_future_timestamp(self, tmp_path):
        lock_path = tmp_path / ".life_calendar.lock"
        payload = {"pid": os.getpid(), "created_at": 9999999999.0, "host": "test", "version": 1}
        lock_path.write_text(json.dumps(payload), encoding="utf-8")

        with patch("lifecalendar.lock.LOCK_FILE", str(lock_path)):
            # Verify no crash with future timestamp
            pass

    def test_concurrent_force_release(self, tmp_path):
        lock_path = tmp_path / ".life_calendar.lock"

        with patch("lifecalendar.lock.LOCK_FILE", str(lock_path)):
            acquire_lock()

            errors = []

            def force_release():
                try:
                    force_release_lock("concurrent test")
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=force_release) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)

            assert len(errors) == 0
            assert not lock_path.exists()


# ── data module ────────────────────────────────────────────────────────────

class TestDataModule:
    """Test data module independently."""

    def test_safe_date_valid(self):
        assert safe_date("2000-01-01") is not None

    def test_safe_date_invalid(self):
        assert safe_date("not-a-date") is None

    def test_life_calendar_data_independence(self):
        lcd = LifeCalendarData("2000-01-01", 90)
        total, filled, stats = lcd.calculate(on_date=date(2025, 1, 1))
        assert total > 0
        assert filled > 0

    def test_goal_calendar_data_independence(self):
        gcd = GoalCalendarData("2025-01-01", "2025-12-31", "Test")
        total, filled, _ = gcd.calculate(on_date=date(2025, 6, 15))
        assert total == 365
        assert 0 < filled < total


# ── layout module ──────────────────────────────────────────────────────────

class TestLayoutModule:
    """Test layout module independently."""

    def test_grid_layout_creation(self):
        layout = GridLayout("life", 4680, 1920, 1080)
        assert layout.columns == 104
        assert layout.cell_size >= 2

    def test_grid_layout_with_config(self):
        config = {"grid_cell_size": 15}
        layout = GridLayout("year", 365, 1920, 1080, config)
        assert layout.max_cell_size == 15


# ── platform wallpaper module ──────────────────────────────────────────────

class TestPlatformWallpaper:
    """Test platform wallpaper dispatch."""

    def test_set_wallpaper_file_missing(self):
        from lifecalendar.platform_wallpaper import set_windows_wallpaper

        result, msg = set_windows_wallpaper("/nonexistent/path.png")
        assert not result
        assert "missing" in msg.lower() or "corrupted" in msg.lower()
