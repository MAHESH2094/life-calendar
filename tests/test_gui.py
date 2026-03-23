"""Tests for GUI entrypoint command modes."""

import json
import time
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

# Some Linux CI images omit tkinter entirely. These tests validate GUI glue,
# so skip this module cleanly when tkinter is unavailable.
tkinter = pytest.importorskip("tkinter")


def _has_tk_display() -> bool:
    """Return True when tkinter can create a root window."""
    try:
        root = tkinter.Tk()
        root.withdraw()
        root.destroy()
        return True
    except tkinter.TclError:
        return False


if not _has_tk_display():
    pytest.skip("No Tk display available in this environment", allow_module_level=True)

import life_calendar_gui  # noqa: E402


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
    with patch("auto_update.main", return_value=7) as mock_auto_update:
        result = life_calendar_gui.main(["--headless-update"])

    assert result == 7
    mock_auto_update.assert_called_once_with([])


class TestGUIAsyncOperations:
    """Integration tests: verify GUI async mechanics for wallpaper operations.

    These tests verify that the threading safeguards work correctly:
    - Buttons are disabled during wallpaper generation
    - Concurrent task submissions are rejected
    - Error handling in worker threads propagates correctly
    """

    def test_set_wallpaper_busy_manages_button_state(self):
        """Verify _set_wallpaper_busy correctly disables/enables buttons."""
        from unittest.mock import MagicMock

        # Use mocks only so the test works on headless CI runners.
        gui = MagicMock()
        gui._wallpaper_task_running = False
        gui.save_settings_button = MagicMock()
        gui.preview_button = MagicMock()
        gui.refresh_button = MagicMock()

        gui._set_wallpaper_busy = life_calendar_gui.LifeCalendarGUI._set_wallpaper_busy.__get__(gui)

        # Test: set busy
        gui._set_wallpaper_busy(True)
        assert gui._wallpaper_task_running is True
        gui.save_settings_button.config.assert_called_with(state="disabled")
        gui.preview_button.config.assert_called_with(state="disabled")
        gui.refresh_button.config.assert_called_with(state="disabled")

        # Test: set not busy
        gui._set_wallpaper_busy(False)
        assert gui._wallpaper_task_running is False
        gui.save_settings_button.config.assert_called_with(state="normal")

    def test_finish_wallpaper_task_clears_state_and_calls_callback(self):
        """Verify _finish_wallpaper_task re-enables buttons and invokes callback."""
        from unittest.mock import MagicMock

        # Don't create Tk root here - just use mocks
        gui = MagicMock()
        gui._wallpaper_task_running = True
        gui.save_settings_button = MagicMock()
        gui.preview_button = MagicMock()
        gui.refresh_button = MagicMock()

        gui._set_wallpaper_busy = life_calendar_gui.LifeCalendarGUI._set_wallpaper_busy.__get__(gui)
        gui._finish_wallpaper_task = life_calendar_gui.LifeCalendarGUI._finish_wallpaper_task.__get__(gui)

        callback_invocations = []

        def on_done(result, error):
            callback_invocations.append((result, error))

        # Finish the task
        gui._finish_wallpaper_task("final_result", None, on_done)

        # Verify: state cleared, buttons enabled, callback called
        assert gui._wallpaper_task_running is False
        gui.save_settings_button.config.assert_called_with(state="normal")
        assert len(callback_invocations) == 1
        assert callback_invocations[0] == ("final_result", None)

    def test_wallpaper_task_flag_prevents_concurrent_execution(self):
        """Verify that the _wallpaper_task_running flag guards against concurrent tasks."""
        from unittest.mock import MagicMock

        # Use mocks instead of Tk to avoid intermittent initialization issues
        gui = MagicMock()
        gui._wallpaper_task_running = False
        gui.save_settings_button = MagicMock()
        gui.preview_button = MagicMock()
        gui.refresh_button = MagicMock()
        gui.set_status = MagicMock()
        gui.root = MagicMock()

        gui._run_wallpaper_task = life_calendar_gui.LifeCalendarGUI._run_wallpaper_task.__get__(gui)
        gui._set_wallpaper_busy = life_calendar_gui.LifeCalendarGUI._set_wallpaper_busy.__get__(gui)

        worker_call_count = 0

        def counting_worker():
            nonlocal worker_call_count
            worker_call_count += 1
            return "OK"

        def on_done(result, error):
            pass

        # First call: flag is False, so it should proceed and set flag to True
        gui._run_wallpaper_task("First", counting_worker, on_done)
        assert gui._wallpaper_task_running is True
        # But don't wait for worker to finish yet

        # Second call while flag is True: should be rejected immediately
        gui._run_wallpaper_task("Second", counting_worker, on_done)

        # Verify rejection message was shown
        assert gui.set_status.called
        call_args = gui.set_status.call_args
        if call_args:
            assert "already running" in call_args[0][0].lower() or "already running" in str(call_args).lower()

        # Simulate task completion
        gui._wallpaper_task_running = False

        # Third call after flag is reset: should proceed again
        gui._run_wallpaper_task("Third", counting_worker, on_done)
        assert gui._wallpaper_task_running is True

    def test_wallpaper_task_worker_exception_handling(self):
        """Verify that exceptions in worker threads are captured and passed to callback."""
        from unittest.mock import MagicMock

        gui = MagicMock()
        gui._wallpaper_task_running = False
        gui.save_settings_button = MagicMock()
        gui.preview_button = MagicMock()
        gui.refresh_button = MagicMock()
        gui.set_status = MagicMock()
        gui.root = MagicMock()

        # Mock root.after to capture the callback function
        captured_callbacks = []
        def mock_after(delay, fn):
            captured_callbacks.append(fn)
            return "job"
        gui.root.after = MagicMock(side_effect=mock_after)

        gui._run_wallpaper_task = life_calendar_gui.LifeCalendarGUI._run_wallpaper_task.__get__(gui)
        gui._set_wallpaper_busy = life_calendar_gui.LifeCalendarGUI._set_wallpaper_busy.__get__(gui)
        gui._finish_wallpaper_task = life_calendar_gui.LifeCalendarGUI._finish_wallpaper_task.__get__(gui)

        callback_data = {}

        def failing_worker():
            raise ValueError("Test worker error")

        def on_done(result, error):
            callback_data["result"] = result
            callback_data["error"] = error

        # Run task with failing worker
        gui._run_wallpaper_task("Failing task", failing_worker, on_done)

        # Wait for worker callback to be queued (avoid fixed-sleep flakiness on CI)
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not captured_callbacks:
            time.sleep(0.01)

        # The callback should have been queued via root.after
        assert len(captured_callbacks) > 0

        # Execute the captured callback
        for callback in captured_callbacks:
            callback()

        # Verify error was passed to callback
        assert callback_data.get("error") is not None
        assert isinstance(callback_data["error"], ValueError)
        assert "Test worker error" in str(callback_data["error"])
        assert callback_data.get("result") is None
