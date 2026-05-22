"""Calendar data models for life, year, and goal progress calculations."""

from __future__ import annotations

import calendar
from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import List, Optional, Tuple


def safe_date(date_str: str, fmt: str = "%Y-%m-%d") -> Optional[datetime]:
    """Safely parse date string with fallback."""
    try:
        return datetime.strptime(date_str, fmt)
    except (ValueError, TypeError):
        return None


class CalendarData(ABC):
    """Base class for calendar calculations."""

    @abstractmethod
    def calculate(self, on_date: Optional[date] = None) -> Tuple[int, int, str]:
        """Returns (total_units, filled_units, stats_text)"""

    @abstractmethod
    def get_title(self) -> str:
        """Returns title text for wallpaper."""

    def get_subtitle(self) -> str:
        """Returns subtitle text for wallpaper (optional, default: empty)."""
        return ""

    @abstractmethod
    def get_legend(self) -> List[Tuple[str, str]]:
        """Returns list of (color, label) tuples."""


class LifeCalendarData(CalendarData):
    """Life-in-weeks calendar data."""

    def __init__(self, dob_str: str, lifespan: int):
        parsed = safe_date(dob_str)
        if parsed is None:
            raise ValueError(f"Invalid date format: {dob_str}. Use YYYY-MM-DD")
        self.dob = parsed
        self.lifespan = max(1, min(lifespan, 150))

    def calculate(self, on_date: Optional[date] = None) -> Tuple[int, int, str]:
        current_day = on_date or date.today()
        days_lived = (current_day - self.dob.date()).days
        weeks_lived = days_lived // 7

        total_days = int(self.lifespan * 365.2425)
        total_weeks = total_days // 7

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
    """Calendar data for current year progress."""

    def __init__(self, current_day: Optional[date] = None):
        self.current_day = current_day

    def calculate(self, on_date: Optional[date] = None) -> Tuple[int, int, str]:
        today = on_date or self.current_day or date.today()
        year = today.year

        is_leap = calendar.isleap(year)
        total_days = 366 if is_leap else 365

        start_of_year = date(year, 1, 1)
        day_of_year = (today - start_of_year).days + 1
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
    """Goal countdown calendar data."""

    def __init__(self, start_str: str, end_str: str, title: str = "", subtitle: str = ""):
        start_date = safe_date(start_str)
        end_date = safe_date(end_str)

        if start_date is None:
            raise ValueError(f"Invalid start date: {start_str}. Use YYYY-MM-DD")
        if end_date is None:
            raise ValueError(f"Invalid end date: {end_str}. Use YYYY-MM-DD")

        self.start = datetime(start_date.year, start_date.month, start_date.day)
        self.end = datetime(end_date.year, end_date.month, end_date.day)

        self.title = title.strip() if title else "GOAL COUNTDOWN"
        self.subtitle = subtitle.strip()

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
