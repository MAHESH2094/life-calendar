"""Local daily companion state and emotional progress helpers."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
import logging
from pathlib import Path
import shutil
from typing import Any, Optional

CONFIG_VERSION = 4
CHECKIN_FILENAME = "daily_checkins.json"
MAX_NOTE_LENGTH = 120
MAX_ALLOWED_NOTE_LENGTH = 1000
VALID_MOODS = ("good", "neutral", "low")
logger = logging.getLogger("daily_companion")

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
    "config_version": CONFIG_VERSION,
    "grid_cell_size": 20,
    "max_note_length": 120,
    "palette": {
        "title": "#f2f2f2",       # Main title and headline
        "stats": "#9a9a9a",       # Stats/secondary text
        "subtitle": "#8a8a8a",    # Subtitle text
        "legend": "#d6d6d6",      # Legend labels
        "lived": "#cfcfcf",       # Passed/Lived cells
        "current": "#ffffff",     # Current cell
        "future": "#3a3a3a",      # Future cells
        "current_progress": "#ffdd00"  # Current progress bar
    },
    "opportunities": [],
    "automation": {
        "startup_enabled": True,
        "wallpaper_refresh_enabled": True,
    },
}


@dataclass(frozen=True)
class TodayMetrics:
    """Derived today-facing metrics shared by the GUI and wallpaper."""

    mode: str
    day_number: int
    total_days: int
    progress_percent: float
    emotional_line: str
    secondary_lines: list[str]
    week_progress: Optional[float] = None

    @property
    def primary_line(self) -> str:
        return f"Day {self.day_number:,} / {self.total_days:,}"

    @property
    def stat_lines(self) -> list[str]:
        return [self.primary_line, *self.secondary_lines, self.emotional_line]


@dataclass(frozen=True)
class CheckinResult:
    """Result of saving a daily check-in."""

    date_key: str
    streak: int
    updated_existing: bool


def safe_parse_date(value: Any) -> Optional[date]:
    """Parse a YYYY-MM-DD string into a date."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_lifespan(value: Any, *, default: int = 90, strict: bool = False) -> int:
    """Parse and validate lifespan with optional strict errors."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        if strict:
            raise ValueError("Lifespan must be a whole number between 1 and 150")
        return default

    if not 1 <= parsed <= 150:
        if strict:
            raise ValueError("Lifespan must be between 1 and 150")
        return default
    return parsed


def sanitize_max_note_length(value: Any, default: int = MAX_NOTE_LENGTH) -> int:
    """Normalize note length limits from config/user data."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed < 1:
        return default
    return min(parsed, MAX_ALLOWED_NOTE_LENGTH)


def merge_config(loaded: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Merge persisted config with current defaults and migrate old versions."""
    merged = deepcopy(DEFAULT_CONFIG)
    if not isinstance(loaded, dict):
        return merged

    for key, value in loaded.items():
        if key == "automation" and isinstance(value, dict):
            merged["automation"].update(value)
        elif key == "palette" and isinstance(value, dict):
            merged["palette"].update(value)
        else:
            merged[key] = value

    for key in ("dob", "goal_start", "goal_end", "goal_title", "goal_subtitle"):
        value = merged.get(key)
        merged[key] = value if isinstance(value, str) else DEFAULT_CONFIG[key]

    try:
        merged["resolution_width"] = int(merged.get("resolution_width", DEFAULT_CONFIG["resolution_width"]))
    except (TypeError, ValueError):
        merged["resolution_width"] = DEFAULT_CONFIG["resolution_width"]

    try:
        merged["resolution_height"] = int(merged.get("resolution_height", DEFAULT_CONFIG["resolution_height"]))
    except (TypeError, ValueError):
        merged["resolution_height"] = DEFAULT_CONFIG["resolution_height"]

    try:
        grid_cell_size = int(merged.get("grid_cell_size", DEFAULT_CONFIG["grid_cell_size"]))
    except (TypeError, ValueError):
        grid_cell_size = DEFAULT_CONFIG["grid_cell_size"]
    merged["grid_cell_size"] = max(2, min(100, grid_cell_size))

    merged["max_note_length"] = sanitize_max_note_length(
        merged.get("max_note_length", DEFAULT_CONFIG["max_note_length"]),
        default=DEFAULT_CONFIG["max_note_length"],
    )

    opportunities = merged.get("opportunities")
    merged["opportunities"] = opportunities if isinstance(opportunities, list) else []

    automation = merged.get("automation")
    if isinstance(automation, dict):
        for key, default_value in DEFAULT_CONFIG["automation"].items():
            current = automation.get(key, default_value)
            automation[key] = current if isinstance(current, bool) else default_value
    else:
        merged["automation"] = deepcopy(DEFAULT_CONFIG["automation"])

    palette = merged.get("palette")
    if isinstance(palette, dict):
        for key, default_value in DEFAULT_CONFIG["palette"].items():
            current = palette.get(key, default_value)
            palette[key] = current if isinstance(current, str) else default_value
    else:
        merged["palette"] = deepcopy(DEFAULT_CONFIG["palette"])

    merged["config_version"] = CONFIG_VERSION
    return merged


def config_has_profile(config: dict[str, Any]) -> bool:
    """Return True when the user has enough data to use the Today dashboard."""
    if not isinstance(config, dict):
        return False

    mode = config.get("mode", "life")
    if mode == "year":
        return True

    if mode == "life":
        dob = safe_parse_date(config.get("dob", ""))
        try:
            lifespan = _parse_lifespan(config.get("lifespan", 0), strict=True)
        except ValueError:
            return False
        return dob is not None and dob <= date.today() and 1 <= lifespan <= 150

    if mode == "goal":
        start = safe_parse_date(config.get("goal_start", ""))
        end = safe_parse_date(config.get("goal_end", ""))
        title = str(config.get("goal_title", "")).strip()
        return start is not None and end is not None and end > start and bool(title)

    return False


def get_today_metrics(config: dict[str, Any], on_date: Optional[date] = None) -> TodayMetrics:
    """Build reflective today-facing progress metrics for the active mode."""
    current_day = on_date or date.today()
    mode = config.get("mode", "life")

    if mode == "life":
        dob = safe_parse_date(config.get("dob", ""))
        if dob is None:
            raise ValueError("Date of birth is required for life mode")

        lifespan = _parse_lifespan(config.get("lifespan", 90), strict=True)
        total_days = max(1, int(lifespan * 365.2425))
        days_lived = max(0, (current_day - dob).days)
        days_lived = min(days_lived, total_days)
        day_number = min(total_days, days_lived + 1)
        progress_percent = round((days_lived / total_days) * 100, 1)
        weeks_remaining = max(0, (total_days - days_lived) // 7)
        week_progress = min(1.0, ((days_lived % 7) + 1) / 7)

        if days_lived > 0 and days_lived % 7 == 0:
            emotional_line = "Another week has passed; make this one count."
        elif weeks_remaining <= 52:
            emotional_line = "A year can pass quietly. Let this day be noticed."
        else:
            emotional_line = "Today still has shape. Give it one worth keeping."

        secondary_lines = [
            f"{progress_percent:g}% of your planned life has passed",
            f"About {weeks_remaining:,} weeks remain",
        ]
        return TodayMetrics(
            mode=mode,
            day_number=day_number,
            total_days=total_days,
            progress_percent=progress_percent,
            emotional_line=emotional_line,
            secondary_lines=secondary_lines,
            week_progress=week_progress,
        )

    if mode == "year":
        year = current_day.year
        start_of_year = date(year, 1, 1)
        total_days = 366 if _is_leap_year(year) else 365
        day_number = min(total_days, (current_day - start_of_year).days + 1)
        progress_percent = round((day_number / total_days) * 100, 1)
        emotional_line = "This year is still being written. Today gets a line."
        secondary_lines = [
            f"{progress_percent:g}% of this year has passed",
            f"{max(0, total_days - day_number):,} days remain in {year}",
        ]
        return TodayMetrics(
            mode=mode,
            day_number=day_number,
            total_days=total_days,
            progress_percent=progress_percent,
            emotional_line=emotional_line,
            secondary_lines=secondary_lines,
        )

    if mode == "goal":
        start = safe_parse_date(config.get("goal_start", ""))
        end = safe_parse_date(config.get("goal_end", ""))
        if start is None or end is None or end <= start:
            raise ValueError("Goal mode requires a valid start and end date")

        total_days = max(1, (end - start).days + 1)
        if current_day < start:
            elapsed_days = 0
            day_number = 1
            remaining_days = max(0, (end - current_day).days + 1)
            emotional_line = "The countdown has not started yet. Use the runway well."
        elif current_day > end:
            elapsed_days = total_days
            day_number = total_days
            remaining_days = 0
            emotional_line = "The window has closed. Carry the lesson into what comes next."
        else:
            elapsed_days = (current_day - start).days + 1
            day_number = min(total_days, elapsed_days)
            remaining_days = max(0, (end - current_day).days + 1)
            emotional_line = "Progress rarely feels dramatic in the moment. Today still matters."

        progress_percent = round((elapsed_days / total_days) * 100, 1)
        secondary_lines = [
            f"{progress_percent:g}% of this goal window has passed",
            f"{remaining_days:,} days remain",
        ]
        return TodayMetrics(
            mode=mode,
            day_number=day_number,
            total_days=total_days,
            progress_percent=progress_percent,
            emotional_line=emotional_line,
            secondary_lines=secondary_lines,
        )

    raise ValueError(f"Unknown mode: {mode}")


class DailyCheckinStore:
    """Persistent local store for once-per-day check-ins."""

    def __init__(self, base_dir: str | Path):
        self.path = Path(base_dir) / CHECKIN_FILENAME
        self.warning_message: Optional[str] = None
        self._data: dict[str, dict[str, dict[str, str]]] = {"entries": {}}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return

        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._recover_empty_store("Daily history was unreadable and has been reset.")
            return

        entries = loaded.get("entries") if isinstance(loaded, dict) else None
        if not isinstance(entries, dict):
            self._recover_empty_store("Daily history was invalid and has been reset.")
            return

        repaired_entries: dict[str, dict[str, str]] = {}
        repaired = False

        for key, value in entries.items():
            if safe_parse_date(key) is None or not isinstance(value, dict):
                repaired = True
                continue

            mood = value.get("mood", "neutral")
            note = value.get("note", "")
            updated_at = value.get("updated_at", "")

            if mood not in VALID_MOODS:
                mood = "neutral"
                repaired = True

            normalized_note = normalize_note(note)
            if normalized_note != note:
                repaired = True

            if not isinstance(updated_at, str):
                updated_at = ""
                repaired = True

            repaired_entries[key] = {
                "mood": mood,
                "note": normalized_note,
                "updated_at": updated_at,
            }

        self._data = {"entries": repaired_entries}

        # FIX: [31] Warn when check-in history becomes large and should be archived.
        if len(repaired_entries) > 1000:
            logger.warning(
                "Daily check-in history has %s entries. Consider archiving older entries.",
                len(repaired_entries),
            )

        if repaired:
            self.warning_message = "Some daily history entries were repaired."
            self._write()

    def _recover_empty_store(self, warning_message: str) -> None:
        self.warning_message = warning_message
        self._data = {"entries": {}}
        self._write()

    def _write(self, payload: Optional[dict[str, dict[str, dict[str, str]]]] = None) -> None:
        """Write data atomically with temp file + rename to prevent corruption."""
        import tempfile
        import os

        write_data = payload if payload is not None else self._data

        # Write to temp file in the same directory
        # Use a simple approach: write to temp file, close it properly, then rename
        temp_dir = self.path.parent
        fd, temp_path = tempfile.mkstemp(dir=temp_dir, suffix='.tmp', text=True)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as temp_file:
                temp_file.write(json.dumps(write_data, indent=2))

            # Atomic rename - either succeeds or fails to completion (on POSIX)
            # On Windows, replace() will overwrite the destination
            self.path.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.replace(temp_path, str(self.path))
            except OSError as e:
                # C5: Fallback for Windows permission issues (read-only destination)
                try:
                    shutil.move(temp_path, str(self.path))
                except Exception as move_err:
                    raise OSError(f"Failed to write check-in file (os.replace failed: {e}, shutil.move failed: {move_err})") from move_err
        except Exception:
            # Clean up temp file if something goes wrong
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def get_entry(self, entry_date: Optional[date] = None) -> Optional[dict[str, str]]:
        key = (entry_date or date.today()).isoformat()
        entry = self._data["entries"].get(key)
        return dict(entry) if entry else None

    def is_checked_in(self, entry_date: Optional[date] = None) -> bool:
        return self.get_entry(entry_date) is not None

    def current_streak(self, today: Optional[date] = None) -> int:
        current_day = today or date.today()
        if self.is_checked_in(current_day):
            return self.calculate_streak(current_day)

        yesterday = current_day - timedelta(days=1)
        if self.is_checked_in(yesterday):
            return self.calculate_streak(yesterday)

        return 0

    def calculate_streak(self, streak_day: Optional[date] = None) -> int:
        target_day = streak_day or date.today()
        target_key = target_day.isoformat()
        if target_key not in self._data["entries"]:
            return 0

        streak = 1
        cursor = target_day
        while True:
            cursor = cursor - timedelta(days=1)
            if cursor.isoformat() not in self._data["entries"]:
                return streak
            streak += 1

    def check_in(
        self,
        mood: str,
        note: str,
        checkin_day: Optional[date] = None,
        current_time: Optional[datetime] = None,
        max_note_length: int = MAX_NOTE_LENGTH,
    ) -> CheckinResult:
        current_day = checkin_day or date.today()
        key = current_day.isoformat()
        normalized_mood = normalize_mood(mood)
        normalized_note = normalize_note(note, max_length=max_note_length)
        timestamp = current_time or datetime.now().astimezone()

        updated_existing = key in self._data["entries"]
        updated_data = {"entries": dict(self._data["entries"])}
        updated_data["entries"][key] = {
            "mood": normalized_mood,
            "note": normalized_note,
            "updated_at": timestamp.isoformat(timespec="seconds"),
        }
        self._write(updated_data)
        self._data = updated_data

        return CheckinResult(
            date_key=key,
            streak=self.calculate_streak(current_day),
            updated_existing=updated_existing,
        )


def normalize_mood(mood: Any) -> str:
    """Normalize mood inputs to one of the three supported values."""
    if isinstance(mood, str) and mood in VALID_MOODS:
        return mood
    return "neutral"


def normalize_note(note: Any, max_length: int = 120) -> str:
    """Normalize note text to a single trimmed line."""
    if not isinstance(note, str):
        return ""
    single_line = " ".join(note.replace("\r", " ").replace("\n", " ").split())
    return single_line[:sanitize_max_note_length(max_length)]


def _is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
