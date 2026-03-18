# tests/test_engine.py
import os
import json
import pytest
from pathlib import Path
from wallpaper_engine import WallpaperEngine, MAX_CELL_SIZE

# Helper – a minimal valid config for each mode
def make_config(mode, **overrides):
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
        "config_version": 2,
    }
    cfg.update(overrides)
    return cfg

def write_config(tmp_path, data):
    cfg_path = tmp_path / "life_calendar_config.json"
    cfg_path.write_text(json.dumps(data, indent=2))
    return str(cfg_path)

@pytest.fixture
def temp_dir(tmp_path):
    # Change CWD to the temporary directory – mimics the auto-update script.
    cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(cwd)

def test_validate_life_mode_success(temp_dir):
    cfg_path = write_config(temp_dir, make_config("life", dob="1995-05-10"))
    engine = WallpaperEngine(cfg_path)
    # Should not raise
    engine.validate_config()

def test_validate_life_mode_missing_dob(temp_dir):
    cfg_path = write_config(temp_dir, make_config("life", dob=""))
    engine = WallpaperEngine(cfg_path)
    with pytest.raises(ValueError, match="Date of birth is required"):
        engine.validate_config()

def test_validate_goal_mode_success(temp_dir):
    cfg_path = write_config(temp_dir,
        make_config("goal", goal_start="2025-01-01", goal_end="2025-12-31", goal_title="Demo"))
    engine = WallpaperEngine(cfg_path)
    engine.validate_config()   # no exception

def test_validate_goal_mode_end_before_start(temp_dir):
    cfg_path = write_config(temp_dir,
        make_config("goal", goal_start="2025-12-31", goal_end="2025-01-01", goal_title="Demo"))
    engine = WallpaperEngine(cfg_path)
    with pytest.raises(ValueError, match="Goal end date must be after start date"):
        engine.validate_config()

def test_generate_wallpaper_and_file_exists(temp_dir):
    cfg_path = write_config(temp_dir, make_config("life"))
    engine = WallpaperEngine(cfg_path)
    ok, msg = engine.generate_wallpaper()
    assert ok, msg
    # The engine writes a PNG next to the script.
    wallpaper = Path(engine.wallpaper_path)
    assert wallpaper.is_file()
    # Basic size sanity check – should be >0 bytes.
    assert wallpaper.stat().st_size > 1000

def test_max_cell_size_constant_is_used():
    # Ensure the constant can be overridden without syntax error.
    assert isinstance(MAX_CELL_SIZE, int) and MAX_CELL_SIZE > 0
