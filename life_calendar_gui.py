"""Life Calendar Daily Companion GUI and packaged app entrypoint."""

from __future__ import annotations

import argparse
import ctypes
from datetime import date
import json
import os
import shutil
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

# Add src to sys.path to resolve lifecalendar package
sys.path.insert(0, str(Path(__file__).parent / "src"))

from lifecalendar.auto_update import get_base_dir as shared_get_base_dir
from lifecalendar.daily_companion import (
    DailyCheckinStore,
    MAX_NOTE_LENGTH,
    VALID_MOODS,
    config_has_profile,
    get_today_metrics,
    merge_config,
    sanitize_max_note_length,
)
from lifecalendar.wallpaper_engine import WallpaperEngine, safe_date
from lifecalendar.windows_automation import sync_windows_tasks


if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def safe_int(value: str, default: int = 0) -> int:
    """Safely convert user input to an int."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def get_base_dir() -> str:
    """Get base directory for source and PyInstaller builds."""
    return str(shared_get_base_dir())


BASE_DIR = get_base_dir()


class LifeCalendarController:
    """Controller for app state, validation, and non-rendering behavior."""

    def __init__(self, base_dir: str, force_today: bool = False):
        self.base_dir = base_dir
        self.config_file = os.path.join(base_dir, "life_calendar_config.json")
        self.checkin_store = DailyCheckinStore(base_dir)
        self.config = self._load_config()
        self.force_today = force_today
        self.today_metrics = None
        self.current_view = "today"

        # GUI refs are populated by LifeCalendarGUI.
        self.root: Any = None
        self.today_frame: Any = None
        self.settings_frame: Any = None
        self.life_mode_frame: Any = None
        self.goal_mode_frame: Any = None

        self.mode_var: Any = None
        self.dob_entry: Any = None
        self.lifespan_entry: Any = None
        self.goal_title_entry: Any = None
        self.goal_subtitle_entry: Any = None
        self.goal_start_entry: Any = None
        self.goal_end_entry: Any = None
        self.width_entry: Any = None
        self.height_entry: Any = None

        self.startup_enabled_var: Any = None
        self.wallpaper_refresh_enabled_var: Any = None
        self.preset_var: Any = None

        self.mood_var: Any = None
        self.note_var: Any = None
        self.primary_line_var: Any = None
        self.secondary_line_1_var: Any = None
        self.secondary_line_2_var: Any = None
        self.emotional_line_var: Any = None

        self.status_var: Any = None
        self.automation_status_var: Any = None
        self.automation_warning = ""

        self.save_settings_button: Any = None
        self.preview_button: Any = None
        self.refresh_button: Any = None
        self._wallpaper_task_running = False

    def _load_config(self) -> dict:
        """Load config with migration to current schema."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as file_handle:
                    loaded = json.load(file_handle)
                return merge_config(loaded)
            return merge_config()
        except (json.JSONDecodeError, OSError):
            return merge_config()

    def _set_entry_value(self, entry: Any, value: Any) -> None:
        if entry is None:
            return
        entry.delete(0, tk.END)
        entry.insert(0, str(value))

    def load_config(self) -> None:
        """Reload config and hydrate available UI fields."""
        self.config = self._load_config()

        if self.mode_var is not None:
            self.mode_var.set(str(self.config.get("mode", "life")))

        self._set_entry_value(self.dob_entry, self.config.get("dob", ""))
        self._set_entry_value(self.lifespan_entry, self.config.get("lifespan", 90))
        self._set_entry_value(self.goal_title_entry, self.config.get("goal_title", ""))
        self._set_entry_value(self.goal_subtitle_entry, self.config.get("goal_subtitle", ""))
        self._set_entry_value(self.goal_start_entry, self.config.get("goal_start", ""))
        self._set_entry_value(self.goal_end_entry, self.config.get("goal_end", ""))
        self._set_entry_value(self.width_entry, self.config.get("resolution_width", 1920))
        self._set_entry_value(self.height_entry, self.config.get("resolution_height", 1080))

        automation = self.config.get("automation", {})
        if self.startup_enabled_var is not None:
            self.startup_enabled_var.set(bool(automation.get("startup_enabled", True)))
        if self.wallpaper_refresh_enabled_var is not None:
            self.wallpaper_refresh_enabled_var.set(bool(automation.get("wallpaper_refresh_enabled", True)))

        self.update_automation_status()

    def save_config(self) -> bool:
        """Persist config and keep backup as best effort."""
        self.config = merge_config(self.config)

        if os.path.exists(self.config_file):
            try:
                shutil.copy2(self.config_file, self.config_file + ".bak")
            except OSError:
                self.set_status("Backup failed. Saving config anyway.", warning=True)

        try:
            import tempfile
            config_dir = os.path.dirname(self.config_file) or "."
            fd, tmp_path = tempfile.mkstemp(dir=config_dir, suffix=".tmp", text=True)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(self.config, fh, indent=2, ensure_ascii=False)
                try:
                    os.replace(tmp_path, self.config_file)
                except OSError:
                    shutil.move(tmp_path, self.config_file)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
            return True
        except OSError as exc:
            self.set_status(f"Failed to save config: {exc}", warning=True)
            return False

    def get_today_metrics(self, today: date) -> tuple[str, str, str, str]:
        """Calculate and return all Today-view metrics."""
        metrics = get_today_metrics(self.config, today)
        secondary_lines = list(metrics.secondary_lines)
        while len(secondary_lines) < 2:
            secondary_lines.append("")
        return (
            metrics.primary_line,
            secondary_lines[0],
            secondary_lines[1],
            metrics.emotional_line,
        )

    def get_checkin_entry(self, today: date) -> dict | None:
        """Retrieve today's check-in."""
        return self.checkin_store.get_entry(today)

    def check_in(self, mood: str, note: str, max_note_length: int) -> tuple[bool, int]:
        """Submit check-in and return update flag and streak."""
        result = self.checkin_store.check_in(mood, note, max_note_length=max_note_length)
        return (result.updated_existing, result.streak)

    def _get_entry_text(self, entry: Any, field_name: str) -> str | None:
        if entry is None:
            self.set_status(f"Missing UI field: {field_name}.", warning=True)
            return None
        return entry.get().strip()

    def validate_and_sync_life_mode(self) -> bool:
        """Validate and sync life mode settings from UI inputs to config."""
        dob = self._get_entry_text(self.dob_entry, "DOB")
        if dob is None:
            return False
        if not dob:
            messagebox.showerror("Validation Error", "Date of birth is required.")
            return False

        dob_value = safe_date(dob)
        if dob_value is None:
            messagebox.showerror("Invalid Date", "Date of birth must use YYYY-MM-DD.")
            return False
        if dob_value.date() > date.today():
            messagebox.showerror("Invalid Date", "Date of birth cannot be in the future.")
            return False

        lifespan_text = self._get_entry_text(self.lifespan_entry, "Lifespan")
        if lifespan_text is None:
            return False

        lifespan = safe_int(lifespan_text, -1)
        if lifespan < 1 or lifespan > 150:
            messagebox.showerror("Validation Error", "Lifespan must be between 1 and 150.")
            return False

        self.config["dob"] = dob
        self.config["lifespan"] = lifespan
        return True

    def validate_and_sync_goal_mode(self) -> bool:
        """Validate and sync goal mode settings from UI inputs to config."""
        title = self._get_entry_text(self.goal_title_entry, "Goal title")
        if title is None:
            return False
        if not title:
            messagebox.showerror("Validation Error", "Goal title is required.")
            return False

        start = self._get_entry_text(self.goal_start_entry, "Goal start")
        end = self._get_entry_text(self.goal_end_entry, "Goal end")
        if start is None or end is None:
            return False

        start_date = safe_date(start)
        end_date = safe_date(end)
        if start_date is None or end_date is None:
            messagebox.showerror("Invalid Date", "Goal dates must use YYYY-MM-DD.")
            return False
        if end_date <= start_date:
            messagebox.showerror("Invalid Dates", "Goal end must be after goal start.")
            return False

        subtitle = self._get_entry_text(self.goal_subtitle_entry, "Goal subtitle")
        if subtitle is None:
            subtitle = ""

        self.config["goal_title"] = title
        self.config["goal_subtitle"] = subtitle
        self.config["goal_start"] = start
        self.config["goal_end"] = end
        return True

    def validate_and_sync_resolution(self) -> bool:
        """Validate and sync resolution settings from UI inputs to config."""
        width_text = self._get_entry_text(self.width_entry, "Resolution width")
        height_text = self._get_entry_text(self.height_entry, "Resolution height")
        if width_text is None or height_text is None:
            return False

        width = safe_int(width_text, -1)
        height = safe_int(height_text, -1)
        if width < 0 or height < 0:
            messagebox.showerror("Resolution Error", "Resolution width and height must be whole numbers.")
            return False
        if width < 800 or height < 600:
            messagebox.showerror("Resolution Error", "Resolution must be at least 800x600.")
            return False
        if width > 7680 or height > 4320:
            messagebox.showerror("Resolution Error", "Resolution must be at most 7680x4320.")
            return False

        self.config["resolution_width"] = width
        self.config["resolution_height"] = height
        return True

    def sync_automation_settings(self) -> None:
        """Sync automation checkbox settings to config."""
        startup_enabled = bool(self.startup_enabled_var.get()) if self.startup_enabled_var is not None else True
        refresh_enabled = (
            bool(self.wallpaper_refresh_enabled_var.get())
            if self.wallpaper_refresh_enabled_var is not None
            else True
        )
        self.config["automation"] = {
            "startup_enabled": startup_enabled,
            "wallpaper_refresh_enabled": refresh_enabled,
        }

    def sync_all_settings(self) -> bool:
        """Validate and sync all UI inputs to config."""
        mode_value = self.mode_var.get().strip().lower() if self.mode_var is not None else "life"
        if mode_value not in {"life", "year", "goal"}:
            messagebox.showerror("Validation Error", "Mode must be life, year, or goal.")
            return False

        self.config["mode"] = mode_value

        if mode_value == "life":
            if not self.validate_and_sync_life_mode():
                return False
        elif mode_value == "goal":
            if not self.validate_and_sync_goal_mode():
                return False

        if not self.validate_and_sync_resolution():
            return False

        self.sync_automation_settings()
        self.config = merge_config(self.config)
        return True

    def save_settings_and_activate(self) -> None:
        """Save settings, generate wallpaper, and apply automation."""
        if not self.sync_all_settings():
            return
        if not self.save_config():
            self.set_status("Unable to save config. Wallpaper update cancelled.", warning=True)
            return

        self._run_wallpaper_task(
            "Generating wallpaper and applying setup...",
            worker=lambda: WallpaperEngine(self.config_file).run_auto(),
            on_done=self._on_save_settings_complete,
        )

    def _on_save_settings_complete(self, result: Any, error: Exception | None) -> None:
        """Handle completion of Save Settings wallpaper job."""
        if error is not None:
            messagebox.showerror("Error", str(error))
            self.set_status(f"Wallpaper generation failed: {type(error).__name__}", warning=True)
            return

        if not bool(result):
            messagebox.showerror("Error", "Failed to generate or set wallpaper. Check wallpaper.log.")
            self.set_status("Wallpaper generation failed.", warning=True)
            return

        self.apply_windows_automation(show_success=False)
        self.load_config()
        self.refresh_today_dashboard()
        self.show_view("today")
        self.set_status("Setup complete. Daily companion is active.", success=True)
        messagebox.showinfo(
            "Setup Complete",
            "Wallpaper updated successfully.\n\nToday dashboard is ready for daily check-ins.",
        )

    def apply_windows_automation(self, show_success: bool = True) -> bool:
        """Apply Windows automation preferences without fatal failures."""
        if sys.platform != "win32":
            self.automation_warning = ""
            self.update_automation_status()
            return True

        success, errors = sync_windows_tasks(self.config, self.base_dir)
        if success:
            self.automation_warning = ""
            self.update_automation_status()
            if show_success:
                self.set_status("Windows automation is active.", success=True)
            return True

        error_details = "\n".join(f"- {error}" for error in errors)
        self.automation_warning = (
            "Automation setup encountered issues. "
            "If you see access denied, run as Administrator and retry."
            f"\n{error_details}"
        )
        self.update_automation_status()
        self.set_status("Automation setup failed. Check retry button.", warning=True)

        messagebox.showwarning(
            "Automation Setup Failed",
            f"Could not set up Windows automation:\n\n{error_details}\n\n"
            "Retry from Settings or run as Administrator.",
        )
        return False

    def update_automation_status(self) -> None:
        """Update automation status label, if present."""
        if self.automation_status_var is None:
            return

        if self.automation_warning:
            self.automation_status_var.set(self.automation_warning)
            return

        automation = self.config.get("automation", {})
        startup_state = "on" if bool(automation.get("startup_enabled", True)) else "off"
        refresh_state = "on" if bool(automation.get("wallpaper_refresh_enabled", True)) else "off"
        self.automation_status_var.set(f"Automation: startup={startup_state}, refresh={refresh_state}")

    def retry_automation(self) -> None:
        """Retry task registration from Settings."""
        if not self.sync_all_settings():
            return
        if not self.save_config():
            self.set_status("Unable to save config. Automation retry cancelled.", warning=True)
            return
        self.apply_windows_automation(show_success=True)

    def preview_wallpaper(self) -> None:
        """Generate preview wallpaper without setting desktop wallpaper."""
        if not self.sync_all_settings():
            return
        if not self.save_config():
            self.set_status("Unable to save config. Preview cancelled.", warning=True)
            return

        def worker() -> tuple[bool, str, str]:
            engine = WallpaperEngine(self.config_file)
            success, message = engine.generate_wallpaper()
            return success, message, engine.wallpaper_path

        self._run_wallpaper_task("Generating preview...", worker=worker, on_done=self._on_preview_complete)

    def _on_preview_complete(self, result: Any, error: Exception | None) -> None:
        """Handle completion of preview generation."""
        if error is not None:
            messagebox.showerror("Error", str(error))
            self.set_status(f"Preview failed: {type(error).__name__}", warning=True)
            return

        if not isinstance(result, tuple) or len(result) != 3:
            self.set_status("Preview failed: worker returned malformed result.", warning=True)
            messagebox.showerror("Error", "Preview failed because worker returned malformed data.")
            return

        success, message, wallpaper_path = result
        if success:
            try:
                from PIL import Image
            except ModuleNotFoundError:
                self.set_status("Preview needs Pillow. Install with: pip install Pillow", warning=True)
                messagebox.showerror("Missing Dependency", "Pillow not installed. Run: pip install Pillow")
                return

            try:
                Image.open(wallpaper_path).show()
                self.set_status("Preview opened.", success=True)
                return
            except OSError as exc:
                self.set_status(f"Preview open failed: {exc}", warning=True)
                messagebox.showerror("Error", f"Unable to open preview image: {exc}")
                return

        messagebox.showerror("Error", message)
        self.set_status(message, warning=True)

    def refresh_wallpaper_now(self) -> None:
        """Refresh wallpaper immediately from current saved config."""
        if not config_has_profile(self.config):
            self.set_status("Finish setup in Settings before refreshing wallpaper.", warning=True)
            self.show_view("settings")
            return

        self._run_wallpaper_task(
            "Refreshing wallpaper...",
            worker=lambda: WallpaperEngine(self.config_file).run_auto(),
            on_done=self._on_refresh_complete,
        )

    def _on_refresh_complete(self, result: Any, error: Exception | None) -> None:
        """Handle completion of manual refresh."""
        if error is not None:
            self.set_status(f"Refresh failed: {type(error).__name__}", warning=True)
            return

        if bool(result):
            self.set_status("Wallpaper refreshed.", success=True)
            return

        self.set_status("Wallpaper refresh failed. Check wallpaper.log.", warning=True)

    def submit_checkin(self) -> None:
        """Save or update today's daily check-in."""
        if not config_has_profile(self.config):
            self.set_status("Finish setup before check-in.", warning=True)
            self.show_view("settings")
            return

        note = self.note_var.get() if self.note_var is not None else ""
        mood = self.mood_var.get() if self.mood_var is not None else "neutral"
        if mood not in VALID_MOODS:
            mood = "neutral"

        max_note_length = sanitize_max_note_length(
            self.config.get("max_note_length", MAX_NOTE_LENGTH),
            default=MAX_NOTE_LENGTH,
        )
        updated, streak = self.check_in(mood, note, max_note_length=max_note_length)

        self.refresh_today_dashboard()
        if updated:
            self.set_status(
                f"Today's check-in was updated. Current streak: {streak} day{'s' if streak != 1 else ''}.",
                success=True,
            )
        else:
            self.set_status(
                f"Checked in for today. Current streak: {streak} day{'s' if streak != 1 else ''}.",
                success=True,
            )

    def reset_defaults(self) -> None:
        """Reset config to defaults and return to settings view."""
        if not messagebox.askyesno("Reset Settings", "Reset app back to default settings?"):
            return

        self.config = merge_config()
        if not self.save_config():
            self.set_status("Failed to reset defaults because config could not be saved.", warning=True)
            return

        self.load_config()
        if self.preset_var is not None:
            self.preset_var.set("1920x1080 (Full HD)")

        self.on_mode_change()
        self.refresh_today_dashboard()
        self.show_view("settings")
        self.set_status("Settings reset to defaults.", success=True)

    def show_help(self) -> None:
        """Show short help dialog."""
        help_text = (
            "Life Calendar Daily Companion\n\n"
            "Today:\n"
            "- Check in once per day with mood and short note.\n"
            "- Watch streak and progress update.\n\n"
            "Settings:\n"
            "- Configure life, year, or goal mode.\n"
            "- Save settings to generate wallpaper and apply automation.\n"
            "- Date format is YYYY-MM-DD.\n\n"
            "Command modes:\n"
            "- --headless-update refreshes wallpaper silently.\n"
            "- --startup-check opens app only if check-in is missing."
        )
        messagebox.showinfo("Help", help_text)

    def set_status(self, msg: str, success: bool = False, warning: bool = False) -> None:
        """Set status message in UI or print fallback."""
        prefix = ""
        if success:
            prefix = "[OK] "
        elif warning:
            prefix = "[WARN] "
        elif msg:
            prefix = "[INFO] "

        text = f"{prefix}{msg}" if msg else ""
        if self.status_var is not None:
            self.status_var.set(text)
        else:
            print(text)

    def show_view(self, view_name: str) -> None:
        """Switch between Today and Settings views."""
        self.current_view = "settings" if view_name == "settings" else "today"
        if self.today_frame is None or self.settings_frame is None:
            return

        if self.current_view == "settings":
            self.settings_frame.tkraise()
        else:
            self.today_frame.tkraise()

    def on_mode_change(self, *_args: Any) -> None:
        """Toggle mode-specific input sections."""
        mode_value = self.mode_var.get().strip().lower() if self.mode_var is not None else "life"
        if self.life_mode_frame is None or self.goal_mode_frame is None:
            return

        if mode_value == "goal":
            self.life_mode_frame.pack_forget()
            if not self.goal_mode_frame.winfo_ismapped():
                self.goal_mode_frame.pack(fill="x", pady=(0, 8))
        else:
            self.goal_mode_frame.pack_forget()
            if not self.life_mode_frame.winfo_ismapped():
                self.life_mode_frame.pack(fill="x", pady=(0, 8))

    def refresh_today_dashboard(self) -> None:
        """Refresh today metrics and existing check-in state in UI."""
        if not config_has_profile(self.config):
            if self.primary_line_var is not None:
                self.primary_line_var.set("Finish setup in Settings to start today tracking.")
            if self.secondary_line_1_var is not None:
                self.secondary_line_1_var.set("")
            if self.secondary_line_2_var is not None:
                self.secondary_line_2_var.set("")
            if self.emotional_line_var is not None:
                self.emotional_line_var.set("")
            return

        try:
            primary, secondary_1, secondary_2, emotional = self.get_today_metrics(date.today())
        except Exception as exc:
            self.set_status(f"Unable to compute today metrics: {exc}", warning=True)
            return

        if self.primary_line_var is not None:
            self.primary_line_var.set(primary)
        if self.secondary_line_1_var is not None:
            self.secondary_line_1_var.set(secondary_1)
        if self.secondary_line_2_var is not None:
            self.secondary_line_2_var.set(secondary_2)
        if self.emotional_line_var is not None:
            self.emotional_line_var.set(emotional)

        entry = self.get_checkin_entry(date.today())
        if isinstance(entry, dict):
            existing_note = str(entry.get("note", ""))
            existing_mood = str(entry.get("mood", "neutral"))
            if self.note_var is not None:
                self.note_var.set(existing_note)
            if self.mood_var is not None and existing_mood in VALID_MOODS:
                self.mood_var.set(existing_mood)

    def _set_wallpaper_busy(self, is_busy: bool) -> None:
        """Set busy flag and disable/enable wallpaper action buttons."""
        self._wallpaper_task_running = is_busy
        state = "disabled" if is_busy else "normal"
        for button_name in ("save_settings_button", "preview_button", "refresh_button"):
            button = getattr(self, button_name, None)
            if button is None:
                continue
            try:
                button.config(state=state)
            except Exception:
                continue

    def _finish_wallpaper_task(self, result: Any, error: Exception | None, on_done: Any) -> None:
        """Clear busy state and forward worker result to callback."""
        self._set_wallpaper_busy(False)
        on_done(result, error)

    def _run_wallpaper_task(self, start_message: str, worker: Any, on_done: Any) -> None:
        """Run wallpaper-related task in a thread and callback on UI thread."""
        if self._wallpaper_task_running:
            self.set_status("Wallpaper task already running. Please wait.", warning=True)
            return

        self.set_status(start_message)
        self._set_wallpaper_busy(True)

        def _worker_thread() -> None:
            result: Any = None
            error: Exception | None = None
            try:
                result = worker()
            except Exception as exc:  # noqa: BLE001
                error = exc

            if self.root is not None:
                try:
                    self.root.after(0, lambda: self._finish_wallpaper_task(result, error, on_done))
                    return
                except Exception:
                    pass

            self._finish_wallpaper_task(result, error, on_done)

        threading.Thread(target=_worker_thread, daemon=True).start()

    def run(self) -> None:
        if self.root is None:
            raise RuntimeError("GUI root not initialized. Instantiate LifeCalendarGUI.")
        self.root.mainloop()


class LifeCalendarGUI(LifeCalendarController):
    """Tkinter GUI application."""

    def __init__(self, force_today: bool = False):
        super().__init__(BASE_DIR, force_today)

        self.root = tk.Tk()
        self.root.title("Life Calendar Daily Companion")
        self.root.geometry("780x760")
        self.root.minsize(680, 620)

        self.mode_var = tk.StringVar(value=str(self.config.get("mode", "life")))
        self.startup_enabled_var = tk.BooleanVar(value=bool(self.config.get("automation", {}).get("startup_enabled", True)))
        self.wallpaper_refresh_enabled_var = tk.BooleanVar(
            value=bool(self.config.get("automation", {}).get("wallpaper_refresh_enabled", True))
        )
        self.preset_var = tk.StringVar(value="1920x1080 (Full HD)")

        self.mood_var = tk.StringVar(value="neutral")
        self.note_var = tk.StringVar(value="")

        self.primary_line_var = tk.StringVar(value="")
        self.secondary_line_1_var = tk.StringVar(value="")
        self.secondary_line_2_var = tk.StringVar(value="")
        self.emotional_line_var = tk.StringVar(value="")

        self.status_var = tk.StringVar(value="")
        self.automation_status_var = tk.StringVar(value="")

        self._build_ui()
        self.load_config()
        self.on_mode_change()
        self.show_view("today")
        self.refresh_today_dashboard()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)

        nav = ttk.Frame(outer)
        nav.pack(fill="x", pady=(0, 8))
        ttk.Button(nav, text="Today", command=lambda: self.show_view("today")).pack(side="left")
        ttk.Button(nav, text="Settings", command=lambda: self.show_view("settings")).pack(side="left", padx=(8, 0))
        ttk.Button(nav, text="Help", command=self.show_help).pack(side="right")

        body = ttk.Frame(outer)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        self.today_frame = ttk.Frame(body)
        self.settings_frame = ttk.Frame(body)
        self.today_frame.grid(row=0, column=0, sticky="nsew")
        self.settings_frame.grid(row=0, column=0, sticky="nsew")

        self._build_today_view(self.today_frame)
        self._build_settings_view(self.settings_frame)

        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=(10, 8))
        ttk.Label(outer, textvariable=self.automation_status_var, justify="left").pack(fill="x")
        ttk.Label(outer, textvariable=self.status_var, justify="left").pack(fill="x", pady=(4, 0))

    def _build_today_view(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, textvariable=self.primary_line_var, font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(4, 8))
        ttk.Label(parent, textvariable=self.secondary_line_1_var).pack(anchor="w")
        ttk.Label(parent, textvariable=self.secondary_line_2_var).pack(anchor="w")
        ttk.Label(parent, textvariable=self.emotional_line_var, wraplength=700, justify="left").pack(anchor="w", pady=(0, 14))

        mood_row = ttk.Frame(parent)
        mood_row.pack(fill="x", pady=(0, 8))
        ttk.Label(mood_row, text="Mood").pack(side="left")
        ttk.Combobox(
            mood_row,
            textvariable=self.mood_var,
            values=list(VALID_MOODS),
            state="readonly",
            width=12,
        ).pack(side="left", padx=(8, 0))

        ttk.Label(parent, text="Note").pack(anchor="w")
        self.note_entry = ttk.Entry(parent, textvariable=self.note_var)
        self.note_entry.pack(fill="x", pady=(0, 10))

        actions = ttk.Frame(parent)
        actions.pack(fill="x")
        ttk.Button(actions, text="Check In", command=self.submit_checkin).pack(side="left")
        self.refresh_button = ttk.Button(actions, text="Refresh Wallpaper", command=self.refresh_wallpaper_now)
        self.refresh_button.pack(side="left", padx=(8, 0))

    def _build_settings_view(self, parent: ttk.Frame) -> None:
        mode_row = ttk.Frame(parent)
        mode_row.pack(fill="x", pady=(4, 8))
        ttk.Label(mode_row, text="Mode").pack(side="left")
        mode_combo = ttk.Combobox(
            mode_row,
            textvariable=self.mode_var,
            values=("life", "year", "goal"),
            state="readonly",
            width=12,
        )
        mode_combo.pack(side="left", padx=(8, 0))
        mode_combo.bind("<<ComboboxSelected>>", self.on_mode_change)

        self.life_mode_frame = ttk.LabelFrame(parent, text="Life / Year")
        self.life_mode_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(self.life_mode_frame, text="DOB (YYYY-MM-DD)").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        self.dob_entry = ttk.Entry(self.life_mode_frame)
        self.dob_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=4)
        ttk.Label(self.life_mode_frame, text="Lifespan").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        self.lifespan_entry = ttk.Entry(self.life_mode_frame)
        self.lifespan_entry.grid(row=1, column=1, sticky="ew", padx=8, pady=4)
        self.life_mode_frame.columnconfigure(1, weight=1)

        self.goal_mode_frame = ttk.LabelFrame(parent, text="Goal")
        self.goal_mode_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(self.goal_mode_frame, text="Title").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        self.goal_title_entry = ttk.Entry(self.goal_mode_frame)
        self.goal_title_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=4)
        ttk.Label(self.goal_mode_frame, text="Subtitle").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        self.goal_subtitle_entry = ttk.Entry(self.goal_mode_frame)
        self.goal_subtitle_entry.grid(row=1, column=1, sticky="ew", padx=8, pady=4)
        ttk.Label(self.goal_mode_frame, text="Start (YYYY-MM-DD)").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        self.goal_start_entry = ttk.Entry(self.goal_mode_frame)
        self.goal_start_entry.grid(row=2, column=1, sticky="ew", padx=8, pady=4)
        ttk.Label(self.goal_mode_frame, text="End (YYYY-MM-DD)").grid(row=3, column=0, sticky="w", padx=8, pady=4)
        self.goal_end_entry = ttk.Entry(self.goal_mode_frame)
        self.goal_end_entry.grid(row=3, column=1, sticky="ew", padx=8, pady=4)
        self.goal_mode_frame.columnconfigure(1, weight=1)

        resolution_frame = ttk.LabelFrame(parent, text="Resolution")
        resolution_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(resolution_frame, text="Width").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        self.width_entry = ttk.Entry(resolution_frame)
        self.width_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=4)
        ttk.Label(resolution_frame, text="Height").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        self.height_entry = ttk.Entry(resolution_frame)
        self.height_entry.grid(row=1, column=1, sticky="ew", padx=8, pady=4)
        resolution_frame.columnconfigure(1, weight=1)

        automation_frame = ttk.LabelFrame(parent, text="Automation")
        automation_frame.pack(fill="x", pady=(0, 8))
        ttk.Checkbutton(automation_frame, text="Run at startup", variable=self.startup_enabled_var).pack(
            anchor="w", padx=8, pady=2
        )
        ttk.Checkbutton(
            automation_frame,
            text="Refresh wallpaper automatically",
            variable=self.wallpaper_refresh_enabled_var,
        ).pack(anchor="w", padx=8, pady=2)

        actions = ttk.Frame(parent)
        actions.pack(fill="x", pady=(6, 0))
        self.save_settings_button = ttk.Button(actions, text="Save Settings", command=self.save_settings_and_activate)
        self.save_settings_button.pack(side="left")
        self.preview_button = ttk.Button(actions, text="Preview", command=self.preview_wallpaper)
        self.preview_button.pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Retry Automation", command=self.retry_automation).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Reset Defaults", command=self.reset_defaults).pack(side="left", padx=(8, 0))


def main(argv: list[str] | None = None) -> int:
    """Entrypoint for normal GUI launches and packaged command modes."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--headless-update", action="store_true")
    parser.add_argument("--startup-check", action="store_true")
    parser.add_argument("--help", action="store_true")
    args, _unknown = parser.parse_known_args(argv)

    if args.help:
        parser.print_help()
        return 0

    if args.headless_update:
        from lifecalendar.auto_update import main as auto_update_main

        return auto_update_main([])

    force_today = False
    if args.startup_check:
        store = DailyCheckinStore(BASE_DIR)
        if store.is_checked_in():
            return 0
        force_today = True

    app = LifeCalendarGUI(force_today=force_today)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
