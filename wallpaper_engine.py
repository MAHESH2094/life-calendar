"""
Wallpaper Engine - Headless Calendar Generation
NO GUI DEPENDENCIES - Scheduler friendly
Version 2.0 - Improved with robust error handling
"""

from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, date
import json
import os
import sys
import platform
import ctypes
import calendar
from abc import ABC, abstractmethod
import logging
from logging.handlers import RotatingFileHandler
from typing import Tuple, List, Optional
import shutil

# ==================== DPI AWARENESS (Windows) ====================
if platform.system() == "Windows":
    try:
        # Modern API (Win8.1+) - best quality
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            # Fallback API (Win7+)
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# ==================== LOGGING SETUP ====================

def get_base_dir() -> str:
    """Get base directory - works for both Python script and PyInstaller EXE"""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller EXE
        return os.path.dirname(sys.executable)
    else:
        # Running as Python script
        return os.path.dirname(os.path.abspath(__file__))

# Use base directory for log file (works in EXE and script modes)
BASE_DIR = get_base_dir()
LOG_PATH = os.path.join(BASE_DIR, "wallpaper.log")
LOCK_FILE = os.path.join(BASE_DIR, ".life_calendar.lock")

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

# Prevent duplicate logs under PyInstaller
logger.propagate = False

# Enable DEBUG mode via environment variable
if os.getenv("LIFECALENDAR_DEBUG") == "1":
    logger.setLevel(logging.DEBUG)


def _is_process_running(pid: int) -> bool:
    """Check if a process with given PID is running"""
    if platform.system() == "Windows":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False
    else:
        # Unix: check if process exists
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


def acquire_lock():
    """Acquire exclusive lock with PID verification and stale detection"""
    # Check for existing lock
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            
            # Check if old process is still running
            if _is_process_running(old_pid):
                raise RuntimeError(f"Another LifeCalendar process is already running (PID: {old_pid})")
            else:
                # Stale lock - remove it
                logger.warning(f"Removing stale lock from dead process (PID: {old_pid})")
                os.remove(LOCK_FILE)
        except (ValueError, IOError):
            # Corrupted lock file - remove it
            try:
                os.remove(LOCK_FILE)
            except OSError:
                pass
    
    # Create new lock atomically
    try:
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
    except FileExistsError:
        # Race condition - another process created it between our check and create
        raise RuntimeError("Another LifeCalendar process is already running")


def release_lock():
    """Release lock file"""
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception:
        pass


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
            primary = monitors[0]
            return primary.width, primary.height
    except ImportError:
        logger.warning("screeninfo not installed, using default resolution")
    except Exception as e:
        logger.warning(f"Could not detect screen resolution: {e}")
    
    return 1920, 1080  # Default fallback


# ==================== DATA LAYER ====================

class CalendarData(ABC):
    """Base class for calendar calculations"""
    
    @abstractmethod
    def calculate(self) -> Tuple[int, int, str]:
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
    
    def calculate(self) -> Tuple[int, int, str]:
        # Always use current time - never cache
        now = datetime.now()
        days_lived = (now.date() - self.dob.date()).days
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
    
    def calculate(self) -> Tuple[int, int, str]:
        # Always use current date - never cache
        today = date.today()
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
        year = date.today().year
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
    
    def calculate(self) -> Tuple[int, int, str]:
        # Always use current time - never cache
        now = datetime.now().date()
        
        total_days = (self.end.date() - self.start.date()).days
        
        if now < self.start.date():
            passed_days = 0
        elif now > self.end.date():
            passed_days = total_days
        else:
            passed_days = (now - self.start.date()).days
        
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
    
    def __init__(self, mode: str, total_units: int, canvas_width: int, canvas_height: int):
        self.mode = mode
        self.total_units = max(1, total_units)  # Prevent division by zero
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        
        self.columns = self._get_columns()
        self.rows = (self.total_units + self.columns - 1) // self.columns
        
        self._calculate_dimensions()
    
    def _get_columns(self) -> int:
        """Determine optimal column count per mode"""
        if self.mode == 'life':
            return 52  # Weeks per year
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
        """Calculate cell size and grid position"""
        # Dynamic margins instead of hardcoded pixels
        available_width = self.canvas_width * 0.9
        available_height = self.canvas_height * 0.75
        
        # Calculate maximum cell size
        max_cell_width = available_width / self.columns
        max_cell_height = available_height / self.rows
        
        # Cell size (cap at 20px for aesthetics)
        self.cell_size = int(min(max_cell_width, max_cell_height, 20))
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
            r'C:\Windows\Fonts\segoeui.ttf',
            r'C:\Windows\Fonts\tahoma.ttf',
        ],
        'Linux': [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/usr/share/fonts/TTF/DejaVuSans.ttf',
        ],
        'Darwin': [
            '/System/Library/Fonts/Helvetica.ttc',
            '/Library/Fonts/Arial.ttf',
        ]
    }
    
    # Class-level font cache
    _font_cache = {}
    
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.img = Image.new('RGB', (width, height), color='#050505')
        self.draw = ImageDraw.Draw(self.img)
        
        self._load_fonts()
    
    def _load_fonts(self) -> None:
        """Load fonts with proper OS detection and fallbacks (uses cache)"""
        system = platform.system()
        
        # Check cache first
        cache_key = f"{system}_fonts"
        if cache_key in WallpaperRenderer._font_cache:
            fonts = WallpaperRenderer._font_cache[cache_key]
            self.title_font = fonts['title']
            self.stats_font = fonts['stats']
            self.legend_font = fonts['legend']
            return
        
        font_paths = self.FONT_PATHS.get(system, self.FONT_PATHS['Linux'])
        
        loaded = False
        for font_path in font_paths:
            try:
                if os.path.exists(font_path):
                    title_font = ImageFont.truetype(font_path, 40)
                    stats_font = ImageFont.truetype(font_path, 18)
                    legend_font = ImageFont.truetype(font_path, 16)
                    
                    # Cache the fonts
                    WallpaperRenderer._font_cache[cache_key] = {
                        'title': title_font,
                        'stats': stats_font,
                        'legend': legend_font
                    }
                    
                    self.title_font = title_font
                    self.stats_font = stats_font
                    self.legend_font = legend_font
                    
                    loaded = True
                    logger.info(f"Loaded fonts from {font_path}")
                    break
            except (IOError, OSError) as e:
                logger.debug(f"Could not load font {font_path}: {e}")
                continue
        
        if not loaded:
            logger.warning("Custom fonts not available, using PIL default with size adjustment")
            # Use PIL's better default font with size hints (won't affect but documents intent)
            try:
                # Try to use a more modern default
                self.title_font = ImageFont.load_default()
                self.stats_font = ImageFont.load_default()
                self.legend_font = ImageFont.load_default()
            except Exception as e:
                logger.error(f"Failed to load default font: {e}")
                # Last resort - None will fallback to PIL default
                self.title_font = None
                self.stats_font = None
                self.legend_font = None
    
    def draw_title(self, text: str, y_position: float) -> None:
        """Draw centered title"""
        bbox = self.draw.textbbox((0, 0), text, font=self.title_font)
        text_width = bbox[2] - bbox[0]
        x = (self.width - text_width) / 2
        self.draw.text((x, y_position), text, fill='#f2f2f2', font=self.title_font)
    
    def draw_stats(self, text: str, y_position: float) -> None:
        """Draw centered stats text"""
        bbox = self.draw.textbbox((0, 0), text, font=self.stats_font)
        text_width = bbox[2] - bbox[0]
        x = (self.width - text_width) / 2
        self.draw.text((x, y_position), text, fill='#9a9a9a', font=self.stats_font)
    
    def draw_subtitle(self, text: str, y_position: float) -> None:
        """Draw centered subtitle text"""
        bbox = self.draw.textbbox((0, 0), text, font=self.stats_font)
        text_width = bbox[2] - bbox[0]
        x = (self.width - text_width) / 2
        self.draw.text((x, y_position), text, fill='#8a8a8a', font=self.stats_font)
    
    def draw_grid(self, layout: GridLayout, total_units: int, filled_units: int) -> None:
        """Draw the calendar grid"""
        for i in range(total_units):
            x, y = layout.get_cell_position(i)
            
            # Determine color - prevent index out of bounds
            if i < filled_units:
                color = '#cfcfcf'  # Passed/Lived
            elif filled_units < total_units and i == filled_units:
                color = '#ffffff'  # Current
            else:
                color = '#3a3a3a'  # Future
            
            self.draw.rectangle(
                [x, y, x + layout.cell_size, y + layout.cell_size],
                fill=color
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
            self.draw.text((x + 25, y_position), label, fill='#d6d6d6', font=self.legend_font)
    
    def save(self, path: str) -> None:
        """Save the image with atomic write to prevent corruption"""
        # Atomic save - write to temp then rename
        temp_path = path + ".tmp"
        try:
            # optimize=True reduces file size significantly
            self.img.save(temp_path, 'PNG', optimize=True)
            os.replace(temp_path, path)
            
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
        self.wallpaper_path = os.path.join(BASE_DIR, "life_calendar_wallpaper.png")
        self.config = self.load_config()
    
    # Default config template for merging
    DEFAULT_CONFIG = {
        "mode": "life",
        "dob": "",
        "lifespan": 90,
        "goal_start": "",
        "goal_end": "",
        "goal_title": "",
        "goal_subtitle": "",
        "resolution_width": 1920,
        "resolution_height": 1080,
        "config_version": 2
    }
    
    def load_config(self) -> dict:
        """Load configuration from file with defaults merge"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                # Merge with defaults to prevent KeyError on missing keys
                merged = self.DEFAULT_CONFIG.copy()
                merged.update(loaded)
                return merged
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
        
        # Mode-specific validation
        if mode == 'life':
            dob = self.config.get('dob', '')
            
            if not dob:
                raise ValueError("Date of birth is required for life calendar")
            
            dob_date = safe_date(dob)
            if dob_date is None:
                raise ValueError("Invalid date of birth format. Use YYYY-MM-DD")
            
            if dob_date > datetime.now():
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
            
            # Data Layer
            if mode == 'life':
                calendar_data = LifeCalendarData(
                    self.config['dob'],
                    int(self.config['lifespan'])
                )
            elif mode == 'year':
                # Auto-update to today's date for year mode - ALWAYS current
                calendar_data = YearCalendarData()
            elif mode == 'goal':
                calendar_data = GoalCalendarData(
                    self.config['goal_start'],
                    self.config['goal_end'],
                    self.config.get('goal_title', ''),
                    self.config.get('goal_subtitle', '')
                )
            else:
                raise ValueError(f"Unknown mode: {mode}")
            
            total_units, filled_units, stats_text = calendar_data.calculate()
            
            # Layout Layer
            layout = GridLayout(mode, total_units, width, height)
            
            # Rendering Layer
            renderer = WallpaperRenderer(width, height)
            renderer.draw_title(calendar_data.get_title(), layout.start_y - 110)
            
            # Draw subtitle if available (all calendars support it now)
            subtitle = calendar_data.get_subtitle()
            if subtitle:
                renderer.draw_subtitle(subtitle, layout.start_y - 75)
                renderer.draw_stats(stats_text, layout.start_y - 45)
            else:
                renderer.draw_stats(stats_text, layout.start_y - 65)
            
            renderer.draw_grid(layout, total_units, filled_units)
            renderer.draw_legend(calendar_data.get_legend(), layout.start_y + layout.grid_height + 50)
            renderer.save(self.wallpaper_path)
            
            return True, f"Wallpaper generated: {self.wallpaper_path}"
            
        except Exception:
            logger.exception("Generation failed")
            return False, "Generation failed"
    
    def set_wallpaper(self) -> Tuple[bool, str]:
        """Set the generated wallpaper with multi-OS support"""
        try:
            system = platform.system()
            
            if system == 'Windows':
                return self._set_windows_wallpaper()
            elif system == 'Darwin':
                return self._set_macos_wallpaper()
            elif system == 'Linux':
                return self._set_linux_wallpaper()
            else:
                return False, f"Unsupported OS: {system}"
            
        except Exception:
            logger.exception("Failed to set wallpaper")
            return False, "Failed to set wallpaper"
    
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
        except Exception:
            pass  # Non-critical - wallpaper is still set
        
        return True, "Wallpaper set successfully"
    
    def _set_macos_wallpaper(self) -> Tuple[bool, str]:
        """Set wallpaper on macOS using temp script file for safe path handling"""
        import tempfile
        import subprocess
        
        abs_path = os.path.abspath(self.wallpaper_path)
        
        # AppleScript with proper quoting
        script = f'''
        tell application "System Events"
            repeat with d in desktops
                set picture of d to "{abs_path}"
            end repeat
        end tell
        '''
        
        script_path = None
        try:
            # Write to temp file to handle paths with spaces/unicode safely
            with tempfile.NamedTemporaryFile(delete=False, suffix=".scpt", mode='w', encoding='utf-8') as f:
                f.write(script)
                script_path = f.name
            
            result = subprocess.run(["osascript", script_path], capture_output=True)
            
            if result.returncode == 0:
                logger.info("Wallpaper set successfully on macOS")
                return True, "Wallpaper set successfully"
            else:
                logger.error(f"osascript failed: {result.stderr.decode()}")
                return False, "osascript failed"
        
        except Exception:
            logger.exception("Failed to set macOS wallpaper")
            return False, "Failed to set macOS wallpaper"
        
        finally:
            # Clean up temp script
            if script_path and os.path.exists(script_path):
                try:
                    os.unlink(script_path)
                except OSError:
                    pass
    
    def _set_linux_wallpaper(self) -> Tuple[bool, str]:
        """Set wallpaper on Linux with multi-DE support and command existence checks"""
        import subprocess
        
        de = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
        session = os.environ.get('DESKTOP_SESSION', '').lower()
        
        # Combine for better detection
        desktop_env = de + session
        
        abs_path = os.path.abspath(self.wallpaper_path)
        
        try:
            success = False
            command_used = None
            
            if 'gnome' in desktop_env or 'ubuntu' in desktop_env or 'unity' in desktop_env:
                # GNOME / Ubuntu / Unity
                if not shutil.which("gsettings"):
                    logger.error("gsettings not installed (required for GNOME/Ubuntu)")
                    return False, "gsettings not installed"
                
                command_used = "gsettings"
                r1 = subprocess.run(['gsettings', 'set', 'org.gnome.desktop.background', 'picture-uri', f'file://{abs_path}'], capture_output=True)
                r2 = subprocess.run(['gsettings', 'set', 'org.gnome.desktop.background', 'picture-uri-dark', f'file://{abs_path}'], capture_output=True)
                success = r1.returncode == 0 or r2.returncode == 0
                
            elif 'kde' in desktop_env or 'plasma' in desktop_env:
                # KDE Plasma
                if not shutil.which("plasma-apply-wallpaperimage"):
                    logger.error("plasma-apply-wallpaperimage not installed (required for KDE)")
                    return False, "plasma-apply-wallpaperimage not installed"
                
                command_used = "plasma-apply-wallpaperimage"
                result = subprocess.run(['plasma-apply-wallpaperimage', abs_path], capture_output=True)
                success = result.returncode == 0
                
            elif 'xfce' in desktop_env:
                # XFCE
                if not shutil.which("xfconf-query"):
                    logger.error("xfconf-query not installed (required for XFCE)")
                    return False, "xfconf-query not installed"
                
                command_used = "xfconf-query"
                result = subprocess.run(['xfconf-query', '-c', 'xfce4-desktop', '-p', '/backdrop/screen0/monitor0/image-path', '-s', abs_path], capture_output=True)
                success = result.returncode == 0
                
            elif 'mate' in desktop_env:
                # MATE
                if not shutil.which("gsettings"):
                    logger.error("gsettings not installed (required for MATE)")
                    return False, "gsettings not installed"
                
                command_used = "gsettings"
                result = subprocess.run(['gsettings', 'set', 'org.mate.background', 'picture-filename', abs_path], capture_output=True)
                success = result.returncode == 0
                
            elif 'cinnamon' in desktop_env:
                # Cinnamon
                if not shutil.which("gsettings"):
                    logger.error("gsettings not installed (required for Cinnamon)")
                    return False, "gsettings not installed"
                
                command_used = "gsettings"
                result = subprocess.run(['gsettings', 'set', 'org.cinnamon.desktop.background', 'picture-uri', f'file://{abs_path}'], capture_output=True)
                success = result.returncode == 0
                
            else:
                # Fallback - try feh (works on most minimal WMs)
                if not shutil.which("feh"):
                    logger.error("feh not installed and no supported desktop environment detected")
                    return False, "No supported wallpaper command found (install feh for minimal WMs)"
                
                command_used = "feh"
                result = subprocess.run(['feh', '--bg-scale', abs_path], capture_output=True)
                success = result.returncode == 0
            
            if success:
                logger.info(f"Wallpaper set successfully on Linux using {command_used}")
                return True, "Wallpaper set successfully"
            else:
                logger.error(f"Wallpaper command '{command_used}' failed. DE: {desktop_env}")
                return False, f"Wallpaper command '{command_used}' failed"
                
        except Exception:
            logger.exception("Failed to set wallpaper on Linux")
            return False, "Failed to set wallpaper on Linux"
    
    def run_auto(self) -> bool:
        """Automated run - for scheduler (NO USER INTERACTION)"""
        try:
            acquire_lock()
            
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
            
        except Exception:
            logger.exception("Auto run failed")
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
            logger.info("Wallpaper updated successfully")
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)