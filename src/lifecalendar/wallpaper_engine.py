"""Wallpaper Engine — backward-compatible re-export shim.

All public names are re-exported from their new canonical modules.
Existing imports like ``from lifecalendar.wallpaper_engine import X`` continue to work.
"""

from __future__ import annotations

# Re-export from new canonical modules for backward compatibility.
from .data import (  # noqa: F401
    CalendarData,
    GoalCalendarData,
    LifeCalendarData,
    YearCalendarData,
    safe_date,
)
from .engine import (  # noqa: F401
    BASE_DIR,
    LOG_PATH,
    WallpaperEngine,
    close_log_handlers,
    get_base_dir,
    get_screen_resolution,
    logger,
)
from .layout import GridLayout  # noqa: F401
from .lock import (  # noqa: F401
    LOCK_FILE,
    acquire_lock,
    force_release_lock,
    release_lock,
)
from .renderer import MAX_GRID_UNITS, MAX_SAFE_PIXELS, WallpaperRenderer  # noqa: F401

__all__ = [
    # lock
    "acquire_lock",
    "force_release_lock",
    "release_lock",
    "LOCK_FILE",
    # data
    "CalendarData",
    "GoalCalendarData",
    "LifeCalendarData",
    "YearCalendarData",
    "safe_date",
    # layout
    "GridLayout",
    # renderer
    "WallpaperRenderer",
    "MAX_GRID_UNITS",
    "MAX_SAFE_PIXELS",
    # engine
    "WallpaperEngine",
    "get_base_dir",
    "get_screen_resolution",
    "BASE_DIR",
    "LOG_PATH",
    "logger",
    "close_log_handlers",
]
