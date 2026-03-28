# tests/test_engine.py
"""
Comprehensive tests for wallpaper_engine.py
Covers all CalendarData subclasses, config validation, GridLayout, and rendering.
"""

import os
import json
import pytest
from pathlib import Path
from datetime import datetime, date, timedelta

from wallpaper_engine import (
    WallpaperEngine,
    LifeCalendarData,
    YearCalendarData,
    GoalCalendarData,
    GridLayout,
    safe_date,
)


# ==================== Helpers ====================

def make_config(mode, **overrides):
    """Build a minimal valid config dict for any mode."""
    cfg = {
        "mode": mode,
        "dob": "1990-01-01",
        "lifespan": 90,
        "goal_start": "2025-01-01",
        "goal_end": "2025-12-31",
        "goal_title": "Test Goal",
        "goal_subtitle": "",
        "resolution_width": 1920,
        "resolution_height": 1080,
        "config_version": 4,
        "palette": {
            "title": "#f2f2f2",
            "stats": "#9a9a9a",
            "subtitle": "#8a8a8a",
            "legend": "#d6d6d6",
            "lived": "#cfcfcf",
            "current": "#ffffff",
            "future": "#3a3a3a",
            "current_progress": "#ffdd00",
        },
        "opportunities": [],
        "automation": {
            "startup_enabled": True,
            "wallpaper_refresh_enabled": True,
        },
    }
    cfg.update(overrides)
    return cfg


def write_config(tmp_path, data):
    """Write config dict to a temporary JSON file and return its path."""
    cfg_path = tmp_path / "life_calendar_config.json"
    cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return str(cfg_path)


@pytest.fixture
def temp_dir(tmp_path):
    """Change CWD to a temporary directory and restore after test."""
    cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(cwd)


# ==================== safe_date ====================

class TestSafeDate:
    def test_valid_date(self):
        result = safe_date("2000-06-15")
        assert result == datetime(2000, 6, 15)

    def test_invalid_format(self):
        assert safe_date("15/06/2000") is None

    def test_empty_string(self):
        assert safe_date("") is None

    def test_none_input(self):
        assert safe_date(None) is None

    def test_custom_format(self):
        result = safe_date("15/06/2000", fmt="%d/%m/%Y")
        assert result == datetime(2000, 6, 15)


# ==================== LifeCalendarData ====================

class TestLifeCalendarData:
    def test_basic_calculation(self):
        lcd = LifeCalendarData("2000-01-01", 90)
        total, filled, stats = lcd.calculate()
        assert total > 0
        assert filled >= 0
        assert filled <= total
        assert "Weeks Lived" in stats

    def test_newborn(self):
        """A person born today has 0 weeks lived."""
        today = date.today().strftime("%Y-%m-%d")
        lcd = LifeCalendarData(today, 90)
        total, filled, _ = lcd.calculate()
        assert filled == 0
        assert total > 0

    def test_lifespan_clamped_to_min(self):
        lcd = LifeCalendarData("1990-01-01", 0)  # Below minimum
        assert lcd.lifespan == 1

    def test_lifespan_clamped_to_max(self):
        lcd = LifeCalendarData("1990-01-01", 200)  # Above maximum
        assert lcd.lifespan == 150

    def test_title(self):
        lcd = LifeCalendarData("1990-01-01", 90)
        assert lcd.get_title() == "YOUR LIFE IN WEEKS"

    def test_legend_has_three_items(self):
        lcd = LifeCalendarData("1990-01-01", 90)
        legend = lcd.get_legend()
        assert len(legend) == 3

    def test_invalid_dob_raises(self):
        with pytest.raises(ValueError, match="Invalid date format"):
            LifeCalendarData("not-a-date", 90)

    def test_subtitle_empty(self):
        lcd = LifeCalendarData("1990-01-01", 90)
        assert lcd.get_subtitle() == ""

    def test_weeks_do_not_exceed_total(self):
        """Very old person: weeks_lived should be capped at total_weeks."""
        lcd = LifeCalendarData("1900-01-01", 50)
        total, filled, _ = lcd.calculate()
        assert filled <= total


# ==================== YearCalendarData ====================

class TestYearCalendarData:
    def test_day_within_range(self):
        ycd = YearCalendarData()
        total, filled, stats = ycd.calculate()
        assert 365 <= total <= 366
        assert 1 <= filled <= total
        assert "Year" in stats

    def test_title_contains_current_year(self):
        ycd = YearCalendarData()
        title = ycd.get_title()
        assert str(date.today().year) in title

    def test_legend(self):
        ycd = YearCalendarData()
        legend = ycd.get_legend()
        assert len(legend) == 3
        labels = [label for _, label in legend]
        assert "Today" in labels


# ==================== GoalCalendarData ====================

class TestGoalCalendarData:
    def test_basic_goal(self):
        gcd = GoalCalendarData("2025-01-01", "2025-12-31", "My Goal")
        total, filled, stats = gcd.calculate()
        assert total == 365  # inclusive end date
        assert "Goal Progress" in stats

    def test_future_goal(self):
        """Goal entirely in the future: 0 days passed."""
        future_start = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
        future_end = (date.today() + timedelta(days=60)).strftime("%Y-%m-%d")
        gcd = GoalCalendarData(future_start, future_end, "Future")
        total, filled, _ = gcd.calculate()
        assert filled == 0

    def test_past_goal(self):
        """Goal entirely in the past: all days passed."""
        gcd = GoalCalendarData("2020-01-01", "2020-12-31", "Past Goal")
        total, filled, _ = gcd.calculate()
        assert filled == total

    def test_single_day_goal(self):
        """Start and end 1 day apart."""
        gcd = GoalCalendarData("2025-06-01", "2025-06-02", "One Day")
        total, filled, _ = gcd.calculate()
        assert total == 2

    def test_end_before_start_raises(self):
        with pytest.raises(ValueError, match="End date must be after start date"):
            GoalCalendarData("2025-12-31", "2025-01-01", "Bad")

    def test_same_start_end_raises(self):
        with pytest.raises(ValueError, match="End date must be after start date"):
            GoalCalendarData("2025-06-01", "2025-06-01", "Same")

    def test_custom_title(self):
        gcd = GoalCalendarData("2025-01-01", "2025-06-01", "My Custom Title")
        assert gcd.get_title() == "MY CUSTOM TITLE"

    def test_subtitle(self):
        gcd = GoalCalendarData("2025-01-01", "2025-06-01", "T", "Sub text")
        assert gcd.get_subtitle() == "Sub text"

    def test_default_title_when_empty(self):
        gcd = GoalCalendarData("2025-01-01", "2025-06-01", "")
        assert gcd.get_title() == "GOAL COUNTDOWN"

    def test_invalid_start_date(self):
        with pytest.raises(ValueError, match="Invalid start date"):
            GoalCalendarData("bad-date", "2025-12-31", "Goal")

    def test_invalid_end_date(self):
        with pytest.raises(ValueError, match="Invalid end date"):
            GoalCalendarData("2025-01-01", "bad-date", "Goal")


# ==================== GridLayout ====================

class TestGridLayout:
    def test_life_mode_landscape_columns(self):
        """Landscape screen should use 104 columns for life mode."""
        layout = GridLayout("life", 4680, 1920, 1080)
        assert layout.columns == 104

    def test_life_mode_portrait_columns(self):
        """Portrait screen should use 52 columns for life mode."""
        layout = GridLayout("life", 4680, 1080, 1920)
        assert layout.columns == 52

    def test_year_mode_columns(self):
        layout = GridLayout("year", 365, 1920, 1080)
        assert layout.columns == 31

    def test_goal_mode_short_goal(self):
        """Short goal uses min(52, total_units)."""
        layout = GridLayout("goal", 30, 1920, 1080)
        assert layout.columns == 30

    def test_goal_mode_long_goal(self):
        """Long goal (>365 days) caps at 60 columns."""
        layout = GridLayout("goal", 500, 1920, 1080)
        assert layout.columns == 60

    def test_cell_position_first(self):
        layout = GridLayout("year", 365, 1920, 1080)
        x, y = layout.get_cell_position(0)
        assert x == layout.start_x
        assert y == layout.start_y

    def test_cell_size_within_bounds(self):
        layout = GridLayout("life", 4680, 1920, 1080)
        assert 2 <= layout.cell_size <= 20  # Default max_cell_size is 20

    def test_zero_total_units_no_crash(self):
        """total_units=0 should be clamped to 1, no division by zero."""
        layout = GridLayout("life", 0, 1920, 1080)
        assert layout.total_units == 1


# ==================== Config Validation ====================

class TestConfigValidation:
    def test_valid_life_config(self, temp_dir):
        cfg_path = write_config(temp_dir, make_config("life", dob="1995-05-10"))
        engine = WallpaperEngine(cfg_path)
        engine.validate_config()  # Should not raise

    def test_missing_dob(self, temp_dir):
        cfg_path = write_config(temp_dir, make_config("life", dob=""))
        engine = WallpaperEngine(cfg_path)
        with pytest.raises(ValueError, match="Date of birth is required"):
            engine.validate_config()

    def test_future_dob(self, temp_dir):
        future = (date.today() + timedelta(days=365)).strftime("%Y-%m-%d")
        cfg_path = write_config(temp_dir, make_config("life", dob=future))
        engine = WallpaperEngine(cfg_path)
        with pytest.raises(ValueError, match="future"):
            engine.validate_config()

    def test_invalid_dob_format(self, temp_dir):
        cfg_path = write_config(temp_dir, make_config("life", dob="15/06/2000"))
        engine = WallpaperEngine(cfg_path)
        with pytest.raises(ValueError, match="Invalid date of birth"):
            engine.validate_config()

    def test_lifespan_too_low(self, temp_dir):
        cfg_path = write_config(temp_dir, make_config("life", lifespan=0))
        engine = WallpaperEngine(cfg_path)
        with pytest.raises(ValueError, match="between 1 and 150"):
            engine.validate_config()

    def test_lifespan_too_high(self, temp_dir):
        cfg_path = write_config(temp_dir, make_config("life", lifespan=200))
        engine = WallpaperEngine(cfg_path)
        with pytest.raises(ValueError, match="between 1 and 150"):
            engine.validate_config()

    def test_lifespan_non_numeric(self, temp_dir):
        cfg_path = write_config(temp_dir, make_config("life", lifespan="abc"))
        engine = WallpaperEngine(cfg_path)
        with pytest.raises(ValueError, match="numeric"):
            engine.validate_config()

    def test_resolution_too_small(self, temp_dir):
        cfg_path = write_config(temp_dir, make_config("life", resolution_width=400, resolution_height=300))
        engine = WallpaperEngine(cfg_path)
        with pytest.raises(ValueError, match="at least 800x600"):
            engine.validate_config()

    def test_resolution_too_large(self, temp_dir):
        cfg_path = write_config(temp_dir, make_config("life", resolution_width=9000, resolution_height=5000))
        engine = WallpaperEngine(cfg_path)
        with pytest.raises(ValueError, match="at most 7680x4320"):
            engine.validate_config()

    def test_palette_missing_required_keys(self, temp_dir):
        cfg_path = write_config(temp_dir, make_config("life", palette={"title": "#ffffff"}))
        engine = WallpaperEngine(cfg_path)
        # merge_config now backfills missing palette keys from defaults.
        engine.validate_config()

    def test_palette_invalid_hex_value(self, temp_dir):
        bad_palette = make_config("life")["palette"]
        bad_palette["title"] = "not-a-color"
        cfg_path = write_config(temp_dir, make_config("life", palette=bad_palette))
        engine = WallpaperEngine(cfg_path)
        with pytest.raises(ValueError, match="must be a hex color"):
            engine.validate_config()

    def test_valid_goal_config(self, temp_dir):
        cfg_path = write_config(temp_dir, make_config(
            "goal", goal_start="2025-01-01", goal_end="2025-12-31", goal_title="Demo"
        ))
        engine = WallpaperEngine(cfg_path)
        engine.validate_config()  # no exception

    def test_goal_end_before_start(self, temp_dir):
        cfg_path = write_config(temp_dir, make_config(
            "goal", goal_start="2025-12-31", goal_end="2025-01-01", goal_title="Demo"
        ))
        engine = WallpaperEngine(cfg_path)
        with pytest.raises(ValueError, match="after start date"):
            engine.validate_config()

    def test_goal_missing_title(self, temp_dir):
        cfg_path = write_config(temp_dir, make_config(
            "goal", goal_start="2025-01-01", goal_end="2025-12-31", goal_title=""
        ))
        engine = WallpaperEngine(cfg_path)
        with pytest.raises(ValueError, match="title is required"):
            engine.validate_config()

    def test_goal_missing_dates(self, temp_dir):
        cfg_path = write_config(temp_dir, make_config(
            "goal", goal_start="", goal_end="", goal_title="Test"
        ))
        engine = WallpaperEngine(cfg_path)
        with pytest.raises(ValueError, match="required"):
            engine.validate_config()

    def test_unknown_mode(self, temp_dir):
        cfg_path = write_config(temp_dir, make_config("unknown_mode"))
        engine = WallpaperEngine(cfg_path)
        # Unknown mode should raise during generation (not validation currently)
        success, _ = engine.generate_wallpaper()
        assert not success

    def test_year_mode_needs_no_extra_config(self, temp_dir):
        cfg_path = write_config(temp_dir, make_config("year"))
        engine = WallpaperEngine(cfg_path)
        engine.validate_config()  # Should not raise

    def test_config_missing_keys_get_defaults(self, temp_dir):
        """Config with only mode should merge with defaults."""
        cfg_path = write_config(temp_dir, {"mode": "year"})
        engine = WallpaperEngine(cfg_path)
        assert engine.config["resolution_width"] == 1920
        assert engine.config["lifespan"] == 90
        assert engine.config["automation"]["startup_enabled"] is True

    def test_invalid_json_raises(self, temp_dir):
        cfg_path = temp_dir / "life_calendar_config.json"
        cfg_path.write_text("{bad json!!", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid JSON"):
            WallpaperEngine(str(cfg_path))

    def test_missing_config_file_raises(self, temp_dir):
        with pytest.raises(FileNotFoundError):
            WallpaperEngine(str(temp_dir / "nonexistent.json"))


# ==================== Wallpaper Generation ====================

class TestWallpaperGeneration:
    def test_generate_life_wallpaper(self, temp_dir):
        cfg_path = write_config(temp_dir, make_config("life"))
        engine = WallpaperEngine(cfg_path)
        ok, msg = engine.generate_wallpaper()
        assert ok, msg
        wallpaper = Path(engine.wallpaper_path)
        assert wallpaper.is_file()
        assert wallpaper.stat().st_size > 1000

    def test_generate_year_wallpaper(self, temp_dir):
        cfg_path = write_config(temp_dir, make_config("year"))
        engine = WallpaperEngine(cfg_path)
        ok, msg = engine.generate_wallpaper()
        assert ok, msg

    def test_generate_goal_wallpaper(self, temp_dir):
        cfg_path = write_config(temp_dir, make_config("goal"))
        engine = WallpaperEngine(cfg_path)
        ok, msg = engine.generate_wallpaper()
        assert ok, msg


# ==================== Configurable grid_cell_size ====================

def test_grid_cell_size_configurable():
    """Test that grid_cell_size is configurable via config"""
    config = {
        "mode": "life",
        "grid_cell_size": 30,
        "resolution_width": 1920,
        "resolution_height": 1080,
    }
    layout = GridLayout("life", 4680, 1920, 1080, config)
    assert layout.max_cell_size == 30
    assert layout.cell_size <= 30

def test_grid_cell_size_clamped():
    """Test that grid_cell_size is clamped to valid range (2-100px)"""
    config_too_small = {"grid_cell_size": -5}
    layout = GridLayout("life", 4680, 1920, 1080, config_too_small)
    assert layout.max_cell_size == 2  # Minimum of 2px

    config_too_large = {"grid_cell_size": 500}
    layout = GridLayout("life", 4680, 1920, 1080, config_too_large)
    assert layout.max_cell_size == 100  # Maximum of 100px
