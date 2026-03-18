"""Tests for GUI entrypoint command modes."""

import json
from datetime import date
from unittest.mock import MagicMock, patch

import life_calendar_gui


def test_startup_check_skips_gui_when_today_is_already_checked_in(tmp_path):
    checkin_path = tmp_path / "daily_checkins.json"
    checkin_path.write_text(
        json.dumps(
            {
                "entries": {
                    date.today().isoformat(): {
                        "mood": "good",
                        "note": "Already done",
                        "updated_at": "2026-03-19T08:00:00+05:30",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    with patch.object(life_calendar_gui, "BASE_DIR", str(tmp_path)), \
         patch.object(life_calendar_gui, "LifeCalendarGUI") as mock_gui:
        result = life_calendar_gui.main(["--startup-check"])

    assert result == 0
    mock_gui.assert_not_called()


def test_startup_check_opens_today_view_when_missing_checkin(tmp_path):
    gui_instance = MagicMock()

    with patch.object(life_calendar_gui, "BASE_DIR", str(tmp_path)), \
         patch.object(life_calendar_gui, "LifeCalendarGUI", return_value=gui_instance) as mock_gui:
        result = life_calendar_gui.main(["--startup-check"])

    assert result == 0
    mock_gui.assert_called_once_with(force_today=True)
    gui_instance.run.assert_called_once()


def test_headless_update_delegates_to_auto_update_main():
    with patch("auto_update.main", return_value=7):
        result = life_calendar_gui.main(["--headless-update"])

    assert result == 7
