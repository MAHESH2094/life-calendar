"""
Wallpaper Engine - Headless Calendar Generation
NO GUI DEPENDENCIES - Scheduler friendly
Version 2.0 - Improved with robust error handling
"""

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
from datetime import datetime, date
import json
import os
import sys
import platform
import ctypes
import calendar
import time
import threading
from abc import ABC, abstractmethod
import logging
from logging.handlers import RotatingFileHandler
import re
from typing import Tuple, List, Optional, Any
import shutil
import signal
import atexit

from auto_update import get_base_dir as shared_get_base_dir
from daily_companion import get_today_metrics, merge_config

# ==================== DPI AWARENESS (Windows) ====================
if sys.platform == "win32":
    try:
        # Modern API (Win8.1+) - best quality
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            # Fallback API (Win7+)
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass  # DPI awareness is optional, continue without logging

# ==================== LOGGING SETUP ====================

# FIX: [29] Centralize base-directory resolution through auto_update.get_base_dir.
def get_base_dir() -> str:
    return str(shared_get_base_dir())

# Use base directory for log file (works in EXE and script modes)
BASE_DIR = get_base_dir()
LOG_PATH = os.path.join(BASE_DIR, "wallpaper.log")
LOCK_FILE = os.path.join(BASE_DIR, ".life_calendar.lock")
DEFAULT_MAX_RUNTIME_MINUTES = 30
STALE_LOCK_TTL_SECONDS = 300
LOCK_ACQUIRE_POLL_SECONDS = 0.25
MAX_GRID_UNITS = 50_000
MAX_SAFE_PIXELS = 7680 * 4320

# Ensure signal hooks are only installed once per process.
_LOCK_SIGNAL_HOOKS_INSTALLED = False

# -----------------------------------------------------------------------
# Configuration constants
# -----------------------------------------------------------------------
# Note: MAX_CELL_SIZE is now configurable via config["grid_cell_size"]
# Default value (20px) is applied during config merge if not specified.

# Rotating log handler (max 500KB, keep 3 backups)
# NOTE: RotatingFileHandler is not fully multiprocess-safe but QueueHandler
# adds complexity. For this app, scheduler runs at midnight and GUI during day,
# so overlap is extremely rare. We use file locking as the primary protection.
logger = logging.getLogger("WallpaperEngine")
logger.setLevel(logging.INFO)

# Only add handler if not already present (prevents duplicates)
if not logger.handlers:
    log_handler = RotatingFileHandler(
        LOG_PATH,
        maxBytes=500_000,
        backupCount=3,
        encoding='utf-8',
        delay=True  # Don't open file until first write - reduces conflicts
    )
    log_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(log_handler)


# FIX: [22] Close and detach log handlers at process exit to reduce log corruption.
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

# Prevent duplicate logs under PyInstaller
logger.propagate = False

# Enable DEBUG mode via environment variable
if os.getenv("LIFECALENDAR_DEBUG") == "1":
    logger.setLevel(logging.DEBUG)


def _is_process_running(pid: int) -> bool:
    """Check if a process with given PID is running"""
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except Exception as e:
            logger.debug(f"Could not check process {pid} status: {e}")
            return False
    else:
        # Unix: check if process exists
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


def _get_lock_max_age_seconds() -> int:
    """Return max lock age in seconds, configurable via env var."""
    value = os.getenv("LIFECALENDAR_MAX_RUNTIME_MINUTES")
    if value:
        try:
            minutes = int(value)
            if minutes > 0:
                return minutes * 60
        except ValueError:
            logger.warning(
                "Invalid LIFECALENDAR_MAX_RUNTIME_MINUTES=%s, using default %s",
                value,
                DEFAULT_MAX_RUNTIME_MINUTES,
            )
    return DEFAULT_MAX_RUNTIME_MINUTES * 60


def _read_lock_info() -> dict[str, Any]:
    """Read lock metadata from disk.

    Supports both legacy lock files (PID as plain text) and JSON metadata.
    """
    with open(LOCK_FILE, "r", encoding="utf-8") as file_handle:
        raw = file_handle.read().strip()

    # Legacy format: plain PID
    if raw.isdigit():
        return {"pid": int(raw), "format": "legacy"}

    # Current format: JSON
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Lock payload must be an object")
    return payload


def _write_lock_info(fd: int) -> None:
    """Write JSON lock metadata to an already-created lock file descriptor."""
    payload = {
        "pid": os.getpid(),
        "created_at": time.time(),
        "host": platform.node() or "unknown",
        "version": 1,
    }
    os.write(fd, json.dumps(payload, separators=(",", ":")).encode("utf-8"))


def _remove_lock_file(reason: str) -> None:
    """Remove lock file and log the reason."""
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
            logger.warning("Removed lock file: %s", reason)
    except OSError as exc:
        logger.warning("Failed to remove lock file (%s): %s", reason, exc)


def install_lock_signal_handlers() -> None:
    """Install signal and exit hooks so locks are cleaned up on termination."""
    global _LOCK_SIGNAL_HOOKS_INSTALLED
    if _LOCK_SIGNAL_HOOKS_INSTALLED:
        return

    if threading.current_thread() is not threading.main_thread():
        return

    def _handle_exit_signal(signum: int, _frame: Any) -> None:
        logger.warning("Received signal %s, releasing lock", signum)
        release_lock()
        raise SystemExit(128 + signum)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _handle_exit_signal)
        except (ValueError, OSError):
            # Not available on every platform/runtime context.
            continue

    atexit.register(release_lock)
    _LOCK_SIGNAL_HOOKS_INSTALLED = True


def force_release_lock(reason: str = "manual force release") -> bool:
    """Force-remove lock file for recovery operations."""
    if os.path.exists(LOCK_FILE):
        _remove_lock_file(reason)
        return True
    return False


def acquire_lock(timeout_seconds: float = 0) -> None:
    """Acquire exclusive lock with PID verification and stale detection."""
    install_lock_signal_handlers()

    start_time = time.monotonic()
    last_error_message = "Another LifeCalendar process is already running"

    while True:
        # Create new lock atomically first (fast path).
        try:
            fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            try:
                _write_lock_info(fd)
            finally:
                os.close(fd)
            logger.info("Lock acquired (PID: %s)", os.getpid())
            return
        except FileExistsError:
            pass
        except OSError as exc:
            logger.error("Failed to create lock file: %s", exc)
            raise RuntimeError(f"Cannot create lock file (permission issue or read-only directory): {exc}") from exc

        # Slow path: inspect and decide whether existing lock is stale.
        try:
            lock_info = _read_lock_info()
            lock_pid = int(lock_info.get("pid"))
            lock_age_seconds = max(0.0, time.time() - os.path.getmtime(LOCK_FILE))
            max_age_seconds = _get_lock_max_age_seconds()

            if not _is_process_running(lock_pid):
                # FIX: [21] Remove dead-process lock only after stale TTL expiry.
                if lock_age_seconds > STALE_LOCK_TTL_SECONDS:
                    _remove_lock_file(
                        f"stale lock from dead process PID {lock_pid} (age {lock_age_seconds:.1f}s)"
                    )
                    continue
                last_error_message = (
                    "Another LifeCalendar process is already running "
                    f"(dead PID: {lock_pid}, age: {lock_age_seconds:.0f}s, waiting for stale TTL)."
                )
            elif lock_age_seconds > max_age_seconds:
                last_error_message = (
                    "Another LifeCalendar process is already running "
                    f"(PID: {lock_pid}, age: {lock_age_seconds / 60:.0f}m, "
                    f"max_runtime: {max_age_seconds / 60:.0f}m)."
                )
            else:
                last_error_message = (
                    "Another LifeCalendar process is already running "
                    f"(PID: {lock_pid}, age: {lock_age_seconds / 60:.0f}m)."
                )

        except (ValueError, json.JSONDecodeError, OSError) as exc:
            # Corrupted lock file: remove once, then retry acquisition.
            _remove_lock_file(f"corrupted or unreadable lock ({exc})")
            continue

        # FIX: [20] Apply bounded lock wait instead of hanging indefinitely.
        if timeout_seconds <= 0:
            raise RuntimeError(last_error_message)

        elapsed = time.monotonic() - start_time
        if elapsed >= timeout_seconds:
            raise RuntimeError(
                f"Timed out after {timeout_seconds:.0f}s waiting for lock. {last_error_message}"
            )

        time.sleep(LOCK_ACQUIRE_POLL_SECONDS)


def release_lock() -> None:
    """Release lock file owned by current process.

    Legacy lock files (plain PID text) are also supported for cleanup.
    """
    try:
        if not os.path.exists(LOCK_FILE):
            return

        try:
            lock_info = _read_lock_info()
            lock_pid = int(lock_info.get("pid"))
        except (ValueError, json.JSONDecodeError, OSError):
            # Corrupted lock: best effort cleanup.
            os.remove(LOCK_FILE)
            return

        if lock_pid == os.getpid():
            os.remove(LOCK_FILE)
            logger.info("Lock released (PID: %s)", os.getpid())
        else:
            logger.debug(
                "Skipping lock release because owner PID %s != current PID %s",
                lock_pid,
                os.getpid(),
            )
    except Exception as exc:
        logger.debug(f"Could not clean up lock file: {exc}")


# ==================== HELPER FUNCTIONS ====================

# NOTE: safe_int removed from engine - use strict validation only
# GUI can use its own safe_int for user input handling


def safe_date(date_str: str, fmt: str = "%Y-%m-%d") -> Optional[datetime]:
    """Safely parse date string with fallback"""
    try:
        return datetime.strptime(date_str, fmt)
    except (ValueError, TypeError):
        return None


def get_screen_resolution() -> Tuple[int, int]:
    """Auto-detect primary screen resolution"""
    try:
        from screeninfo import get_monitors
        monitors = get_monitors()
        if monitors:
            primary = next((m for m in monitors if getattr(m, "is_primary", False)), monitors[0])
            if primary.width >= 800 and primary.height >= 600:
                logger.info(f"Detected screen resolution: {primary.width}x{primary.height}")
                return primary.width, primary.height
            else:
                logger.warning(f"Detected resolution {primary.width}x{primary.height} is below 800x600 minimum, using fallback")
    except ImportError:
        logger.warning("screeninfo not installed, using default resolution")
    except Exception as e:
        logger.warning(f"Could not detect screen resolution: {e}")

    logger.info("Using fallback resolution: 1920x1080")
    return 1920, 1080  # Default fallback


# ==================== DATA LAYER ====================

class CalendarData(ABC):
    """Base class for calendar calculations"""

    @abstractmethod
    def calculate(self, on_date: Optional[date] = None) -> Tuple[int, int, str]:
        """Returns (total_units, filled_units, stats_text)"""
        pass

    @abstractmethod
    def get_title(self) -> str:
        """Returns title text for wallpaper"""
        pass

    def get_subtitle(self) -> str:
        """Returns subtitle text for wallpaper (optional, default: empty)"""
        return ""

    @abstractmethod
    def get_legend(self) -> List[Tuple[str, str]]:
        """Returns list of (color, label) tuples"""
        pass


class LifeCalendarData(CalendarData):
    def __init__(self, dob_str: str, lifespan: int):
        parsed = safe_date(dob_str)
        if parsed is None:
            raise ValueError(f"Invalid date format: {dob_str}. Use YYYY-MM-DD")
        self.dob = parsed
        self.lifespan = max(1, min(lifespan, 150))  # Clamp 1-150 years

    def calculate(self, on_date: Optional[date] = None) -> Tuple[int, int, str]:
        current_day = on_date or date.today()
        days_lived = (current_day - self.dob.date()).days
        weeks_lived = days_lived // 7

        # Calculate total weeks using accurate calendar math (365.2425 days/year)
        total_days = int(self.lifespan * 365.2425)
        total_weeks = total_days // 7

        # Ensure weeks_lived doesn't exceed total
        weeks_lived = min(weeks_lived, total_weeks)

        stats = f"Weeks Lived: {weeks_lived} | Remaining: {total_weeks - weeks_lived} | Total: {total_weeks}"
        return total_weeks, weeks_lived, stats

    def get_title(self) -> str:
        return "YOUR LIFE IN WEEKS"

    def get_legend(self) -> List[Tuple[str, str]]:
        return [
            ('#cfcfcf', 'Lived'),
            ('#ffffff', 'Current Week'),
            ('#3a3a3a', 'Future')
        ]


class YearCalendarData(CalendarData):
    """Calendar data for current year progress (always uses system date)"""

    def __init__(self, current_day: Optional[date] = None):
        self.current_day = current_day

    def calculate(self, on_date: Optional[date] = None) -> Tuple[int, int, str]:
        today = on_date or self.current_day or date.today()
        year = today.year

        # Handle leap years correctly
        is_leap = calendar.isleap(year)
        total_days = 366 if is_leap else 365

        # Normalize to midnight to avoid off-by-one errors
        start_of_year = date(year, 1, 1)

        # Add 1 to get actual day number (Jan 1 = Day 1, not Day 0)
        day_of_year = (today - start_of_year).days + 1

        # Clamp to prevent overflow on Dec 31
        day_of_year = min(day_of_year, total_days)

        percentage = round((day_of_year / total_days) * 100, 1)
        stats = f"Year {year} Progress: Day {day_of_year} of {total_days} ({percentage}%)"

        return total_days, day_of_year, stats

    def get_title(self) -> str:
        year = (self.current_day or date.today()).year
        return f"YEAR PROGRESS {year}"

    def get_legend(self) -> List[Tuple[str, str]]:
        return [
            ('#cfcfcf', 'Passed'),
            ('#ffffff', 'Today'),
            ('#3a3a3a', 'Remaining')
        ]


class GoalCalendarData(CalendarData):
    def __init__(self, start_str: str, end_str: str, title: str = "", subtitle: str = ""):
        start_date = safe_date(start_str)
        end_date = safe_date(end_str)

        if start_date is None:
            raise ValueError(f"Invalid start date: {start_str}. Use YYYY-MM-DD")
        if end_date is None:
            raise ValueError(f"Invalid end date: {end_str}. Use YYYY-MM-DD")

        # Normalize to midnight
        self.start = datetime(start_date.year, start_date.month, start_date.day)
        self.end = datetime(end_date.year, end_date.month, end_date.day)

        # Store title and subtitle
        self.title = title.strip() if title else "GOAL COUNTDOWN"
        self.subtitle = subtitle.strip()

        # Validation
        if self.end <= self.start:
            raise ValueError("End date must be after start date")

    def calculate(self, on_date: Optional[date] = None) -> Tuple[int, int, str]:
        now = on_date or date.today()

        total_days = (self.end.date() - self.start.date()).days + 1

        if now < self.start.date():
            passed_days = 0
        elif now > self.end.date():
            passed_days = total_days
        else:
            passed_days = (now - self.start.date()).days + 1

        percentage = round((passed_days / total_days) * 100, 1) if total_days > 0 else 0
        stats = f"Goal Progress: {passed_days} of {total_days} days ({percentage}%)"

        return total_days, passed_days, stats

    def get_title(self) -> str:
        return self.title.upper()

    def get_subtitle(self) -> str:
        return self.subtitle

    def get_legend(self) -> List[Tuple[str, str]]:
        return [
            ('#cfcfcf', 'Completed'),
            ('#ffffff', 'Today'),
            ('#3a3a3a', 'Remaining')
        ]


# ==================== LAYOUT LAYER ====================

class GridLayout:
    """Calculates grid dimensions and positioning"""

    def __init__(self, mode: str, total_units: int, canvas_width: int, canvas_height: int, config: Optional[dict[str, Any]] = None):
        self.mode = mode
        self.total_units = max(1, total_units)  # Prevent division by zero
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height

        # Get grid_cell_size from config, or use default
        self.max_cell_size = 20
        if config and isinstance(config.get("grid_cell_size"), int):
            self.max_cell_size = max(2, min(100, config["grid_cell_size"]))  # Cap between 2-100px

        self.columns = self._get_columns()
        self.rows = (self.total_units + self.columns - 1) // self.columns

        self._calculate_dimensions()

    def _get_columns(self) -> int:
        """Determine optimal column count per mode, landscape-aware"""
        if self.mode == 'life':
            # On landscape screens, use more columns to fill horizontal space
            # Standard: 52 weeks/year. But 52 cols × ~90 rows = portrait grid.
            # Double columns on landscape canvases for better space usage.
            aspect = self.canvas_width / self.canvas_height if self.canvas_height > 0 else 1
            if aspect >= 1.3:
                # Landscape screen: use 104 columns (2 years per row)
                # This gives ~45 rows instead of ~90, fitting landscape much better
                return 104
            return 52  # Portrait/square screens keep traditional layout
        elif self.mode == 'year':
            return 31  # Days per month style
        elif self.mode == 'goal':
            # Adaptive: cap at 60 columns to prevent overflow
            if self.total_units <= 365:
                return min(52, self.total_units)
            else:
                return 60
        return 52

    def _calculate_dimensions(self) -> None:
        """Calculate cell size and grid position - landscape-aware"""
        # Dynamic margins instead of hardcoded pixels
        available_width = self.canvas_width * 0.9
        available_height = self.canvas_height * 0.75

        # Fit to available WIDTH first (landscape-friendly)
        # Account for gaps between cells
        cell_from_width = (available_width - (self.columns - 1) * 2) / self.columns

        # Check if resulting grid height fits
        cell_from_height = (available_height - (self.rows - 1) * 2) / self.rows

        # Use the smaller of the two to ensure grid fits both dimensions
        # Cap at max_cell_size from config for consistent aesthetics
        self.cell_size = int(min(cell_from_width, cell_from_height, self.max_cell_size))
        self.cell_size = max(self.cell_size, 2)  # Floor at 2px minimum
        self.gap = int(max(2, self.cell_size * 0.15))

        # Grid dimensions
        self.grid_width = int(self.columns * self.cell_size + (self.columns - 1) * self.gap)
        self.grid_height = int(self.rows * self.cell_size + (self.rows - 1) * self.gap)

        # Center position
        self.start_x = int((self.canvas_width - self.grid_width) / 2)
        self.start_y = int((self.canvas_height - self.grid_height) / 2 + 60)

    def get_cell_position(self, index: int) -> Tuple[float, float]:
        """Get (x, y) position for cell at index"""
        row = index // self.columns
        col = index % self.columns

        x = self.start_x + col * (self.cell_size + self.gap)
        y = self.start_y + row * (self.cell_size + self.gap)

        return x, y


# ==================== RENDERING LAYER ====================

class WallpaperRenderer:
    """Handles all drawing operations"""

    # Font paths for each OS
    FONT_PATHS = {
        'Windows': [
            r'C:\Windows\Fonts\arial.ttf',
            r'C:\Windows\Fonts\SegoeUI.ttf',
            r'C:\Windows\Fonts\segoeui.ttf',
            r'C:\Windows\Fonts\tahoma.ttf',
        ],
        'Linux': [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/usr/share/fonts/TTF/DejaVuSans.ttf',
            '/usr/local/share/fonts/DejaVuSans.ttf',
            '~/.fonts/DejaVuSans.ttf',
        ],
        'Darwin': [
            '/System/Library/Fonts/Helvetica.ttc',
            '/System/Library/Fonts/Supplemental/Arial.ttf',
            '/Library/Fonts/Arial.ttf',
            '~/Library/Fonts/Arial.ttf',
        ]
    }

    # Class-level font cache (so fonts are loaded only once per process)
    _font_cache = {}

    def __init__(self, width: int, height: int, config: Optional[dict[str, Any]] = None):
        self.width = width
        self.height = height
        self.config = config or {}

        # FIX: [25] Warn when requested image size exceeds the known safe memory threshold.
        if width * height > MAX_SAFE_PIXELS:
            logger.warning(
                "Large canvas requested (%sx%s = %s px) exceeds guard threshold %s px; proceeding.",
                width,
                height,
                width * height,
                MAX_SAFE_PIXELS,
            )

        self.img = Image.new('RGB', (width, height), color='#050505')
        self.draw = ImageDraw.Draw(self.img)

        # Load palette colors from config with fallbacks
        palette = self.config.get("palette", {})
        self.title_color = palette.get("title", "#f2f2f2")
        self.stats_color = palette.get("stats", "#9a9a9a")
        self.subtitle_color = palette.get("subtitle", "#8a8a8a")
        self.legend_color = palette.get("legend", "#d6d6d6")
        self.passed_color = palette.get("lived", "#cfcfcf")
        self.current_color = palette.get("current", "#ffffff")
        self.future_color = palette.get("future", "#3a3a3a")
        self.highlight_color = palette.get("current_progress", "#ffdd00")

        self._load_fonts()

    def _load_fonts(self) -> None:
        """Load fonts with proper OS detection and robust fall-backs (uses cache)"""
        if sys.platform == "win32":
            system = "Windows"
        elif sys.platform == "darwin":
            system = "Darwin"
        else:
            system = "Linux"

        def _load_font(font_path: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
            if font_path.lower().endswith(".ttc"):
                # FIX: [14] Use explicit face index for TTC collections.
                return ImageFont.truetype(font_path, size, index=0)
            return ImageFont.truetype(font_path, size)

        # Check cache first
        cache_key = f"{system}_fonts"
        if cache_key in WallpaperRenderer._font_cache:
            fonts = WallpaperRenderer._font_cache[cache_key]
            self.title_font = fonts['title']
            self.headline_font = fonts['headline']
            self.stats_font = fonts['stats']
            self.subtitle_font = fonts['subtitle']
            self.legend_font = fonts['legend']
            return

        font_paths = self.FONT_PATHS.get(system, self.FONT_PATHS['Linux'])

        loaded = False
        for font_path in font_paths:
            try:
                expanded_path = os.path.expanduser(font_path)
                if os.path.exists(expanded_path):
                    title_font = _load_font(expanded_path, 40)
                    headline_font = _load_font(expanded_path, 26)
                    stats_font = _load_font(expanded_path, 18)
                    subtitle_font = _load_font(expanded_path, 16)
                    legend_font = _load_font(expanded_path, 16)

                    # Cache the fonts
                    WallpaperRenderer._font_cache[cache_key] = {
                        'title': title_font,
                        'headline': headline_font,
                        'stats': stats_font,
                        'subtitle': subtitle_font,
                        'legend': legend_font
                    }

                    self.title_font = title_font
                    self.headline_font = headline_font
                    self.stats_font = stats_font
                    self.subtitle_font = subtitle_font
                    self.legend_font = legend_font

                    loaded = True
                    logger.info(f"Loaded fonts from {expanded_path}")
                    break
            except (IOError, OSError) as e:
                logger.debug(f"Could not load font {expanded_path}: {e}")
                continue

        if not loaded:
            logger.warning("Custom fonts not available – falling back to Pillow's default")
            # -----------------------------------------------------------------------
            # If we fall out of the loop without loading any custom font, we fall back
            # to Pillow's built-in default font. The previous implementation set the
            # attributes to ``None`` which could raise ``TypeError`` when Pillow tries
            # to draw text. Keeping a real ImageFont instance (even the simplest one)
            # guarantees the renderer never crashes.
            # -----------------------------------------------------------------------
            default_font = ImageFont.load_default()
            self.title_font = default_font
            self.headline_font = default_font
            self.stats_font = default_font
            self.subtitle_font = default_font
            self.legend_font = default_font

    def draw_title(self, text: str, y_position: float) -> None:
        """Draw centered title"""
        bbox = self.draw.textbbox((0, 0), text, font=self.title_font)
        text_width = bbox[2] - bbox[0]
        x = (self.width - text_width) / 2
        self.draw.text((x, y_position), text, fill=self.title_color, font=self.title_font)

    def draw_stats(self, text: str, y_position: float) -> None:
        """Draw centered stats text"""
        bbox = self.draw.textbbox((0, 0), text, font=self.stats_font)
        text_width = bbox[2] - bbox[0]
        x = (self.width - text_width) / 2
        self.draw.text((x, y_position), text, fill=self.stats_color, font=self.stats_font)

    def draw_subtitle(self, text: str, y_position: float) -> None:
        """Draw centered subtitle text"""
        bbox = self.draw.textbbox((0, 0), text, font=self.subtitle_font)
        text_width = bbox[2] - bbox[0]
        x = (self.width - text_width) / 2
        self.draw.text((x, y_position), text, fill=self.subtitle_color, font=self.subtitle_font)

    def draw_headline_stat(self, text: str, y_position: float) -> None:
        """Draw the primary stat line with stronger emphasis."""
        bbox = self.draw.textbbox((0, 0), text, font=self.headline_font)
        text_width = bbox[2] - bbox[0]
        x = (self.width - text_width) / 2
        self.draw.text((x, y_position), text, fill=self.title_color, font=self.headline_font)

    def draw_grid(
        self,
        layout: GridLayout,
        total_units: int,
        filled_units: int,
        current_progress: Optional[float] = None,
    ) -> None:
        """Draw the calendar grid using colors from config palette"""
        # FIX: [24] Short-circuit oversized grids that can hang low-resource machines.
        if total_units > MAX_GRID_UNITS:
            logger.warning(
                "Skipping grid render because total_units=%s exceeds MAX_GRID_UNITS=%s",
                total_units,
                MAX_GRID_UNITS,
            )
            return

        # Use palette colors loaded in __init__
        for i in range(total_units):
            x, y = layout.get_cell_position(i)

            # Determine color - prevent index out of bounds
            if i < filled_units:
                color = self.passed_color  # Passed/Lived
            elif filled_units < total_units and i == filled_units:
                color = self.current_color  # Current
            else:
                color = self.future_color  # Future

            self.draw.rectangle(
                [x, y, x + layout.cell_size, y + layout.cell_size],
                fill=color
            )

            if filled_units < total_units and i == filled_units:
                self.draw.rectangle(
                    [x, y, x + layout.cell_size, y + layout.cell_size],
                    outline=self.highlight_color,
                    width=2,
                )
                if current_progress is not None:
                    progress_width = max(2, int(layout.cell_size * max(0.0, min(1.0, current_progress))))
                    bar_top = y + layout.cell_size - max(3, layout.cell_size // 4)
                    self.draw.rectangle(
                        [x + 1, bar_top, x + progress_width, y + layout.cell_size],
                        fill=self.highlight_color,
                    )

    def draw_legend(self, legend_items: List[Tuple[str, str]], y_position: float) -> None:
        """Draw legend"""
        item_width = 140
        total_width = len(legend_items) * item_width
        start_x = (self.width - total_width) / 2

        for idx, (color, label) in enumerate(legend_items):
            x = start_x + idx * item_width

            # Draw color box
            self.draw.rectangle([x, y_position, x + 15, y_position + 15], fill=color)

            # Draw label
            self.draw.text((x + 25, y_position), label, fill=self.legend_color, font=self.legend_font)

    def save(self, path: str) -> None:
        """Save the image with atomic write to prevent corruption"""
        # Atomic save - write to temp then rename
        temp_path = path + ".tmp"
        try:
            # optimize=True reduces file size significantly
            self.img.save(temp_path, 'PNG', optimize=True)
            try:
                os.replace(temp_path, path)
            except OSError as exc:
                # Cross-device writes can fail when temp and destination mount differ.
                logger.debug(f"os.replace failed ({exc}); falling back to shutil.move")
                shutil.move(temp_path, path)

            # Verify file was created successfully
            if not os.path.exists(path):
                raise RuntimeError("Wallpaper file not created")
        except Exception:
            # Always clean up temp file if something fails
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except OSError:
                pass
            raise


# ==================== ENGINE LAYER ====================

class WallpaperEngine:
    """Headless wallpaper generation and setting - NO GUI"""

    def __init__(self, config_file: str = "life_calendar_config.json"):
        # Resolve to absolute path
        if not os.path.isabs(config_file):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            config_file = os.path.join(base_dir, config_file)

        self.config_file = config_file
        # The wallpaper is written next to the executable/script.
        # ``BASE_DIR`` already points at the correct absolute directory
        # (script folder or the PyInstaller bundle directory).
        self.wallpaper_path = os.path.join(BASE_DIR, "life_calendar_wallpaper.png")
        self.config = self.load_config()

    # Default config template for merging
    DEFAULT_CONFIG = merge_config()

    def load_config(self) -> dict[str, Any]:
        """Load configuration from file with defaults merge"""
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
        except Exception as e:
            raise Exception(f"Failed to load config: {e}")

    def validate_config(self) -> None:
        """Validate configuration before generation - STRICT validation, no silent fallbacks"""
        mode = self.config.get('mode', 'life')

        # Resolution validation - STRICT (no safe_int)
        try:
            width = int(self.config["resolution_width"])
            height = int(self.config["resolution_height"])
        except (KeyError, ValueError, TypeError):
            raise ValueError("Resolution must be numeric integers")

        if width < 800 or height < 600:
            raise ValueError("Resolution must be at least 800x600")
        if width > 7680 or height > 4320:
            raise ValueError("Resolution must be at most 7680x4320")

        # Palette validation - fail fast on malformed or partial palettes.
        palette = self.config.get("palette")
        if not isinstance(palette, dict):
            raise ValueError("Palette must be an object with required color keys")

        required_palette_keys = set(self.DEFAULT_CONFIG["palette"].keys())
        missing_keys = sorted(required_palette_keys - set(palette.keys()))
        if missing_keys:
            raise ValueError(f"Palette is missing required keys: {', '.join(missing_keys)}")

        hex_color = re.compile(r"^#[0-9a-fA-F]{6}$")
        for key in required_palette_keys:
            value = palette.get(key)
            if not isinstance(value, str) or not hex_color.match(value):
                raise ValueError(f"Palette value for '{key}' must be a hex color like #AABBCC")

        # Mode-specific validation
        if mode == 'life':
            dob = self.config.get('dob', '')

            if not dob:
                raise ValueError("Date of birth is required for life calendar")

            dob_date = safe_date(dob)
            if dob_date is None:
                raise ValueError("Invalid date of birth format. Use YYYY-MM-DD")

            if dob_date.date() > date.today():
                raise ValueError("Date of birth cannot be in the future")

            # Lifespan validation - STRICT (no safe_int)
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
        """Generate wallpaper from config"""
        try:
            # Validate first
            self.validate_config()

            mode = self.config['mode']
            width = int(self.config['resolution_width'])
            height = int(self.config['resolution_height'])
            current_day = date.today()

            # Data Layer
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

            # Layout Layer
            layout = GridLayout(mode, total_units, width, height, self.config)

            # Rendering Layer
            renderer = WallpaperRenderer(width, height, self.config)
            renderer.draw_title(calendar_data.get_title(), layout.start_y - 140)

            # Draw subtitle if available (all calendars support it now)
            subtitle = calendar_data.get_subtitle()
            stat_start_y = layout.start_y - 88
            if subtitle:
                renderer.draw_subtitle(subtitle, layout.start_y - 112)
                stat_start_y = layout.start_y - 78

            renderer.draw_headline_stat(today_metrics.primary_line, stat_start_y)
            renderer.draw_stats(today_metrics.secondary_lines[0], stat_start_y + 34)
            renderer.draw_stats(today_metrics.secondary_lines[1], stat_start_y + 58)
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

        # FIX: [28] Catch explicit hot-path failures and log full traceback.
        except (OSError, ValueError, UnidentifiedImageError) as e:
            logger.exception(f"Generation failed: {e}")
            return False, f"Generation failed: {str(e)[:100]}"

    def set_wallpaper(self) -> Tuple[bool, str]:
        """Set the generated wallpaper with multi-OS support"""
        try:
            # FIX: [29] Use explicit sys.platform checks for OS dispatch.
            if sys.platform == 'win32':
                return self._set_windows_wallpaper()
            elif sys.platform == 'darwin':
                return self._set_macos_wallpaper()
            elif sys.platform.startswith('linux'):
                return self._set_linux_wallpaper()
            else:
                return False, f"Unsupported OS: {sys.platform}"

        # FIX: [28] Catch explicit hot-path failures and log full traceback.
        except (OSError, ValueError, UnidentifiedImageError) as e:
            logger.exception(f"Failed to set wallpaper: {e}")
            return False, f"Failed to set wallpaper: {str(e)[:100]}"

    def _set_windows_wallpaper(self) -> Tuple[bool, str]:
        """Set wallpaper on Windows with verification and broadcast refresh"""
        abs_path = os.path.abspath(self.wallpaper_path)

        # Verify file exists and is valid
        if not os.path.isfile(abs_path):
            return False, "Wallpaper file missing"

        if os.path.getsize(abs_path) < 1000:
            return False, "Wallpaper file corrupted (too small)"

        # Set wallpaper via SystemParametersInfo
        result = ctypes.windll.user32.SystemParametersInfoW(20, 0, abs_path, 3)

        if not result:
            return False, "Windows API call failed"

        # Force Windows to refresh wallpaper via broadcast
        # This prevents the wallpaper from sometimes not updating visually
        try:
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            SMTO_ABORTIFHUNG = 0x0002
            ctypes.windll.user32.SendMessageTimeoutW(
                HWND_BROADCAST, WM_SETTINGCHANGE, 0, 0, SMTO_ABORTIFHUNG, 5000, None
            )
        except Exception as e:
            logger.debug(f"Could not broadcast wallpaper change notification: {e}")  # Non-critical

        return True, "Wallpaper set successfully"

    def _set_macos_wallpaper(self) -> Tuple[bool, str]:
        """Set wallpaper on macOS using osascript args for robust path handling"""
        import subprocess

        abs_path = os.path.abspath(self.wallpaper_path)
        try:
            script = (
                "on run argv\n"
                "set wallpaperPath to quoted form of POSIX path of (item 1 of argv)\n"
                "tell application \"System Events\"\n"
                "repeat with d in desktops\n"
                "set picture of d to POSIX file (item 1 of argv) as text\n"
                "end repeat\n"
                "end tell\n"
                "end run"
            )
            result = subprocess.run(["osascript", "-e", script, abs_path], capture_output=True, text=True)

            if result.returncode == 0:
                logger.info("Wallpaper set successfully on macOS")
                return True, "Wallpaper set successfully"
            else:
                logger.error(f"osascript failed: {result.stderr}")
                return False, "osascript failed"

        except Exception as e:
            logger.exception(f"Failed to set macOS wallpaper: {e}")
            return False, f"Failed to set macOS wallpaper: {str(e)[:100]}"

    def _set_linux_wallpaper(self) -> Tuple[bool, str]:
        """Set wallpaper on Linux with multi-DE support and fallback strategies"""
        import subprocess

        de = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
        session = os.environ.get('DESKTOP_SESSION', '').lower()

        # Use whichever is available, preferring XDG_CURRENT_DESKTOP
        desktop_env = (de or session).lower()

        if desktop_env:
            logger.info(f"Detected Linux desktop: XDG_CURRENT_DESKTOP={os.environ.get('XDG_CURRENT_DESKTOP', 'unknown')}, DESKTOP_SESSION={os.environ.get('DESKTOP_SESSION', 'unknown')}")
        else:
            logger.info("No desktop environment detected - will try fallback methods")

        abs_path = os.path.abspath(self.wallpaper_path)

        try:
            success = False
            command_used = None

            if 'gnome' in desktop_env or 'ubuntu' in desktop_env or 'unity' in desktop_env:
                # GNOME / Ubuntu / Unity
                if not shutil.which("gsettings"):
                    logger.error("gsettings not installed (required for GNOME/Ubuntu). Install with: sudo apt install gsettings-desktop-schemas")
                    return False, "gsettings not installed"

                command_used = "gsettings"
                r1 = subprocess.run(['gsettings', 'set', 'org.gnome.desktop.background', 'picture-uri', f'file://{abs_path}'], capture_output=True)
                r2 = subprocess.run(['gsettings', 'set', 'org.gnome.desktop.background', 'picture-uri-dark', f'file://{abs_path}'], capture_output=True)
                success = r1.returncode == 0 or r2.returncode == 0

            elif 'kde' in desktop_env or 'plasma' in desktop_env:
                # KDE Plasma
                if not shutil.which("plasma-apply-wallpaperimage"):
                    logger.error("plasma-apply-wallpaperimage not installed (required for KDE). Install with: sudo apt install plasma-workspace")
                    return False, "plasma-apply-wallpaperimage not installed"

                command_used = "plasma-apply-wallpaperimage"
                result = subprocess.run(['plasma-apply-wallpaperimage', abs_path], capture_output=True)
                success = result.returncode == 0

            elif 'xfce' in desktop_env:
                # XFCE
                if not shutil.which("xfconf-query"):
                    logger.error("xfconf-query not installed (required for XFCE). Install with: sudo apt install xfconf")
                    return False, "xfconf-query not installed"

                command_used = "xfconf-query"
                result = subprocess.run(['xfconf-query', '-c', 'xfce4-desktop', '-p', '/backdrop/screen0/monitor0/image-path', '-s', abs_path], capture_output=True)
                success = result.returncode == 0

            elif 'mate' in desktop_env:
                # MATE
                if not shutil.which("gsettings"):
                    logger.error("gsettings not installed (required for MATE). Install with: sudo apt install mate-desktop")
                    return False, "gsettings not installed"

                command_used = "gsettings"
                result = subprocess.run(['gsettings', 'set', 'org.mate.background', 'picture-filename', abs_path], capture_output=True)
                success = result.returncode == 0

            elif 'cinnamon' in desktop_env:
                # Cinnamon
                if not shutil.which("gsettings"):
                    logger.error("gsettings not installed (required for Cinnamon). Install with: sudo apt install cinnamon")
                    return False, "gsettings not installed"

                command_used = "gsettings"
                result = subprocess.run(['gsettings', 'set', 'org.cinnamon.desktop.background', 'picture-uri', f'file://{abs_path}'], capture_output=True)
                success = result.returncode == 0

            else:
                # Fallback 1: Try xwallpaper (common X11 method)
                if shutil.which("xwallpaper"):
                    logger.info("Trying xwallpaper fallback")
                    command_used = "xwallpaper"
                    result = subprocess.run(['xwallpaper', '--zoom', abs_path], capture_output=True)
                    success = result.returncode == 0

                # Fallback 2: Try feh (universal window manager solution)
                if not success and shutil.which("feh"):
                    logger.info("Trying feh (window manager fallback)")
                    command_used = "feh"
                    result = subprocess.run(['feh', '--bg-scale', abs_path], capture_output=True)
                    success = result.returncode == 0

                # Fallback 3: Try nitrogen if installed
                if not success and shutil.which("nitrogen"):
                    logger.info("Trying nitrogen fallback")
                    command_used = "nitrogen"
                    result = subprocess.run(['nitrogen', '--set-zoom-fill', '--save', abs_path], capture_output=True)
                    success = result.returncode == 0

                # Fallback 4: If all else fails, inform user
                if not success:
                    logger.error("No supported wallpaper method found. Install one of: xwallpaper, feh, nitrogen, or a supported desktop environment (GNOME/KDE/XFCE/MATE/Cinnamon)")
                    return False, "No supported wallpaper command found - install xwallpaper/feh/nitrogen or use a supported desktop environment"

            if success:
                logger.info(f"Wallpaper set successfully on Linux using {command_used}")
                return True, "Wallpaper set successfully"
            else:
                logger.error(f"Wallpaper command '{command_used}' failed. DE: {desktop_env}")
                return False, f"Wallpaper command '{command_used}' failed"

        except Exception as e:
            logger.exception(f"Failed to set wallpaper on Linux: {e}")
            return False, f"Failed to set wallpaper on Linux: {str(e)[:100]}"

    def run_auto(self) -> bool:
        """Automated run - for scheduler (NO USER INTERACTION)"""
        try:
            # FIX: [20] Use bounded lock wait for scheduled/background runs.
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


# ==================== CLI ENTRY POINT ====================

if __name__ == "__main__":
    import sys

    logger.info("Life Calendar Wallpaper Engine v2.0")

    try:
        engine = WallpaperEngine()
        logger.info(f"Mode: {engine.config.get('mode', 'unknown')}")
        logger.info(f"Resolution: {engine.config.get('resolution_width')}x{engine.config.get('resolution_height')}")

        success = engine.run_auto()

        if not success:
            logger.error("Wallpaper update failed - check wallpaper.log")
            sys.exit(1)
        else:
            sys.exit(0)

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
