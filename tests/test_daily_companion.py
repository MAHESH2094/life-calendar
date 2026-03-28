"""Tests for the daily companion data layer."""

import json
from datetime import date, datetime
import pytest

from daily_companion import DailyCheckinStore, get_today_metrics, merge_config


def test_merge_config_adds_automation_defaults():
    merged = merge_config({"mode": "year"})
    assert merged["config_version"] == 4
    assert merged["automation"]["startup_enabled"] is True
    assert merged["automation"]["wallpaper_refresh_enabled"] is True


def test_merge_config_backfills_partial_palette():
    merged = merge_config({"palette": {"title": "#123456"}})
    assert merged["palette"]["title"] == "#123456"
    assert "current_progress" in merged["palette"]
    assert "future" in merged["palette"]


def test_life_metrics_use_day_count_and_weeks_remaining():
    metrics = get_today_metrics(
        {
            "mode": "life",
            "dob": "2000-01-01",
            "lifespan": 90,
        },
        on_date=date(2000, 1, 10),
    )

    assert metrics.primary_line == "Day 10 / 32,871"
    assert "planned life has passed" in metrics.secondary_lines[0]
    assert "weeks remain" in metrics.secondary_lines[1]
    assert len(metrics.secondary_lines) == 2
    assert metrics.week_progress is not None


def test_metrics_keep_emotional_line_separate_from_secondary_lines():
    metrics = get_today_metrics(
        {
            "mode": "year",
        },
        on_date=date(2026, 3, 29),
    )

    assert metrics.emotional_line
    assert metrics.emotional_line not in metrics.secondary_lines
    assert metrics.stat_lines[-1] == metrics.emotional_line


def test_checkins_increment_streak_and_same_day_edits_do_not(tmp_path):
    store = DailyCheckinStore(tmp_path)
    day_one = date(2026, 3, 19)
    day_two = date(2026, 3, 20)

    first = store.check_in("good", "Walked outside", checkin_day=day_one, current_time=datetime(2026, 3, 19, 8, 0))
    second = store.check_in("neutral", "Did focused work", checkin_day=day_two, current_time=datetime(2026, 3, 20, 8, 0))
    updated = store.check_in("low", "Still showed up", checkin_day=day_two, current_time=datetime(2026, 3, 20, 21, 0))

    assert first.streak == 1
    assert second.streak == 2
    assert updated.updated_existing is True
    assert updated.streak == 2
    assert store.current_streak(day_two) == 2


def test_corrupt_store_is_reset_with_warning(tmp_path):
    store_path = tmp_path / "daily_checkins.json"
    store_path.write_text("{bad json", encoding="utf-8")

    store = DailyCheckinStore(tmp_path)

    assert store.warning_message is not None
    assert store.get_entry() is None
    repaired = json.loads(store_path.read_text(encoding="utf-8"))
    assert repaired == {"entries": {}}


def test_checkin_write_failure_does_not_mutate_memory(tmp_path):
    store = DailyCheckinStore(tmp_path)

    def fail_write(*_args, **_kwargs):
        raise OSError("disk full")

    store._write = fail_write  # type: ignore[method-assign]

    with pytest.raises(OSError):
        store.check_in("good", "Will fail", checkin_day=date(2026, 3, 21))

    assert store.get_entry(date(2026, 3, 21)) is None


def test_merge_config_sanitizes_invalid_max_note_length():
    merged = merge_config({"max_note_length": "abc"})
    assert merged["max_note_length"] == 120
