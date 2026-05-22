"""Wallpaper engine orchestrator — config, validation, generation, and auto-run."""

from __future__ import annotations

import atexit
import json
import logging
import os
import re
from datetime import date
from logging.handlers import RotatingFileHandler
from typing import Any, Tuple

from PIL import UnidentifiedImageError

from .auto_update import get_base_dir as shared_get_base_dir
from .daily_companion import get_today_metrics, merge_config
from .data import GoalCalendarData, LifeCalendarData, YearCalendarData, safe_date
from .layout import GridLayout
from .lock import acquire_lock, release_lock
from .platform_wallpaper import set_wallpaper
from .renderer import WallpaperRenderer

# Pre-computed set of required palette keys for config validation.
_REQUIRED_PALETTE_KEYS: frozenset[str] = frozenset(merge_config()["palette"].keys())

# ── logging setup ──────────────────────────────────────────────────────────

def get_base_dir() -> str:
    return str(shared_get_base_dir())


BASE_DIR = get_base_dir()
LOG_PATH = os.path.join(BASE_DIR, "wallpaper.log")

logger = logging.getLogger("WallpaperEngine")
logger.setLevel(logging.INFO)

if not logger.handlers:
    log_handler = RotatingFileHandler(
        LOG_PATH,
        maxBytes=500_000,
        backupCount=3,
        encoding='utf-8',
        delay=True,
    )
    log_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(log_handler)


def close_log_handlers() -> None:
    for handler in list(logger.handlers):
        try:
            handler.flush()
            handler.close()
        except OSError:
            pass
        finally:
            logger.removeHandler(handler)


atexit.register(close_log_handlers)

logger.propagate = False

if os.getenv("LIFECALENDAR_DEBUG") == "1":
    logger.setLevel(logging.DEBUG)


# ── helpers ────────────────────────────────────────────────────────────────

def get_screen_resolution() -> Tuple[int, int]:
    """Auto-detect primary screen resolution."""
    try:
        from screeninfo import get_monitors
        monitors = get_monitors()
        if monitors:
            primary = next((m for m in monitors if getattr(m, "is_primary", False)), monitors[0])
            if primary.width >= 800 and primary.height >= 600:
                logger.info(f"Detected screen resolution: {primary.width}x{primary.height}")
                return primary.width, primary.height
            else:
                logger.warning(
                    f"Detected resolution {primary.width}x{primary.height} is below 800x600 minimum, using fallback"
                )
    except ImportError:
        logger.warning("screeninfo not installed, using default resolution")
    except Exception as e:
        logger.warning(f"Could not detect screen resolution: {e}")

    logger.info("Using fallback resolution: 1920x1080")
    return 1920, 1080


# ── engine ─────────────────────────────────────────────────────────────────

class WallpaperEngine:
    """Headless wallpaper generation and setting — NO GUI."""

    def __init__(self, config_file: str = "life_calendar_config.json"):
        if not os.path.isabs(config_file):
            config_file = os.path.join(BASE_DIR, config_file)

        self.config_file = config_file
        self.wallpaper_path = os.path.join(BASE_DIR, "life_calendar_wallpaper.png")
        self.config = self.load_config()

    def load_config(self) -> dict[str, Any]:
        """Load configuration from file with defaults merge."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                return merge_config(loaded)
            else:
                raise FileNotFoundError(f"Config file not found: {self.config_file}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file: {e}")
        except FileNotFoundError:
            raise
        except OSError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to load config: {e}") from e

    def validate_config(self) -> None:
        """Validate configuration before generation — STRICT, no silent fallbacks."""
        mode = self.config.get('mode', 'life')

        try:
            width = int(self.config["resolution_width"])
            height = int(self.config["resolution_height"])
        except (KeyError, ValueError, TypeError):
            raise ValueError("Resolution must be numeric integers")

        if width < 800 or height < 600:
            raise ValueError("Resolution must be at least 800x600")
        if width > 7680 or height > 4320:
            raise ValueError("Resolution must be at most 7680x4320")

        palette = self.config.get("palette")
        if not isinstance(palette, dict):
            raise ValueError("Palette must be an object with required color keys")

        required_palette_keys = set(_REQUIRED_PALETTE_KEYS)
        missing_keys = sorted(required_palette_keys - set(palette.keys()))
        if missing_keys:
            raise ValueError(f"Palette is missing required keys: {', '.join(missing_keys)}")

        hex_color = re.compile(r"^#[0-9a-fA-F]{6}$")
        for key in required_palette_keys:
            value = palette.get(key)
            if not isinstance(value, str) or not hex_color.match(value):
                raise ValueError(f"Palette value for '{key}' must be a hex color like #AABBCC")

        if mode == 'life':
            dob = self.config.get('dob', '')

            if not dob:
                raise ValueError("Date of birth is required for life calendar")

            dob_date = safe_date(dob)
            if dob_date is None:
                raise ValueError("Invalid date of birth format. Use YYYY-MM-DD")

            if dob_date.date() > date.today():
                raise ValueError("Date of birth cannot be in the future")

            try:
                lifespan = int(self.config["lifespan"])
            except (KeyError, ValueError, TypeError):
                raise ValueError("Lifespan must be numeric")

            if lifespan < 1 or lifespan > 150:
                raise ValueError("Lifespan must be between 1 and 150 years")

        elif mode == 'goal':
            start = self.config.get('goal_start', '')
            end = self.config.get('goal_end', '')
            title = self.config.get('goal_title', '')

            if not start or not end:
                raise ValueError("Goal start and end dates are required")

            if not title.strip():
                raise ValueError("Goal title is required")

            start_date = safe_date(start)
            end_date = safe_date(end)

            if start_date is None:
                raise ValueError("Invalid goal start date format. Use YYYY-MM-DD")
            if end_date is None:
                raise ValueError("Invalid goal end date format. Use YYYY-MM-DD")

            if end_date <= start_date:
                raise ValueError("Goal end date must be after start date")

    def generate_wallpaper(self) -> Tuple[bool, str]:
        """Generate wallpaper from config."""
        try:
            self.validate_config()

            mode = self.config['mode']
            width = int(self.config['resolution_width'])
            height = int(self.config['resolution_height'])
            current_day = date.today()

            if mode == 'life':
                calendar_data = LifeCalendarData(
                    self.config['dob'],
                    int(self.config['lifespan'])
                )
            elif mode == 'year':
                calendar_data = YearCalendarData(current_day=current_day)
            elif mode == 'goal':
                calendar_data = GoalCalendarData(
                    self.config['goal_start'],
                    self.config['goal_end'],
                    self.config.get('goal_title', ''),
                    self.config.get('goal_subtitle', '')
                )
            else:
                raise ValueError(f"Unknown mode: {mode}")

            total_units, filled_units, _stats_text = calendar_data.calculate(on_date=current_day)
            today_metrics = get_today_metrics(self.config, on_date=current_day)

            layout = GridLayout(mode, total_units, width, height, self.config)

            renderer = WallpaperRenderer(width, height, self.config)
            renderer.draw_title(calendar_data.get_title(), layout.start_y - 140)

            subtitle = calendar_data.get_subtitle()
            stat_start_y = layout.start_y - 88
            if subtitle:
                renderer.draw_subtitle(subtitle, layout.start_y - 112)
                stat_start_y = layout.start_y - 78

            renderer.draw_headline_stat(today_metrics.primary_line, stat_start_y)
            for idx, line in enumerate(today_metrics.secondary_lines[:2]):
                renderer.draw_stats(line, stat_start_y + 34 + idx * 24)
            renderer.draw_subtitle(today_metrics.emotional_line, stat_start_y + 86)

            renderer.draw_grid(
                layout,
                total_units,
                filled_units,
                current_progress=today_metrics.week_progress if mode == 'life' else None,
            )
            renderer.draw_legend(calendar_data.get_legend(), layout.start_y + layout.grid_height + 50)
            renderer.save(self.wallpaper_path)

            return True, f"Wallpaper generated: {self.wallpaper_path}"

        except (OSError, ValueError, KeyError, TypeError, UnidentifiedImageError) as e:
            logger.exception(f"Generation failed: {e}")
            return False, f"Generation failed: {str(e)[:100]}"

    def set_wallpaper(self) -> Tuple[bool, str]:
        """Set the generated wallpaper with multi-OS support."""
        try:
            return set_wallpaper(self.wallpaper_path)
        except (OSError, ValueError, UnidentifiedImageError) as e:
            logger.exception(f"Failed to set wallpaper: {e}")
            return False, f"Failed to set wallpaper: {str(e)[:100]}"

    def run_auto(self) -> bool:
        """Automated run — for scheduler (NO USER INTERACTION)."""
        try:
            acquire_lock(timeout_seconds=10)

            success, message = self.generate_wallpaper()
            if not success:
                logger.error(message)
                return False

            success, message = self.set_wallpaper()
            if not success:
                logger.error(message)
                return False

            logger.info("Wallpaper updated successfully")
            return True

        except Exception as e:
            logger.exception(f"Auto run failed: {e}")
            return False

        finally:
            release_lock()
