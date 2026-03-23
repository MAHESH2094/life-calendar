"""Life Calendar Daily Companion GUI and packaged app entrypoint."""

from __future__ import annotations

import argparse
import ctypes
from datetime import date, datetime
import json
import os
import platform
import shutil
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from daily_companion import (
    DailyCheckinStore,
    MAX_NOTE_LENGTH,
    VALID_MOODS,
    config_has_profile,
    get_today_metrics,
    merge_config,
)
from wallpaper_engine import WallpaperEngine, get_screen_resolution, safe_date
from windows_automation import sync_windows_tasks


if platform.system() == "Windows":
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
    """Get the base directory for both source and PyInstaller builds."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = get_base_dir()


class LifeCalendarGUI:
    """Tkinter GUI for the daily companion experience."""

    # D2: Centralized UI color constants - easy to maintain light/dark themes
    COLORS = {
        "bg_primary": "#050505",      # Main background (near black)
        "bg_secondary": "#101010",    # Card/container background
        "bg_tertiary": "#141414",     # Panel background
        "bg_nav": "#050505",          # Navigation bar
        "bg_nav_active": "#1f2d21",   # Active nav button (dark green)
        "bg_nav_active_settings": "#1f2731",
        "bg_nav_inactive": "#151515", # Inactive nav area
        "text_primary": "#f2f2f2",    # Main text
        "text_secondary": "#a0a0a0",  # Secondary text
        "text_soft": "#d8d8d8",
        "text_info": "#a6b7d1",
        "text_hint": "#7c8799",
        "text_note_counter": "#6f7f96",
        "text_muted": "#6a6a6a",      # Muted/disabled text
        "border": "#2a2a2a",          # Borders
        "accent_success": "#4caf50",  # Success (green)
        "accent_success_soft": "#88c090",
        "accent_warning": "#ff9800",  # Warning (orange)
        "accent_error": "#f44336",    # Error (red)
        "button_secondary": "#181818",
        "button_secondary_active": "#202020",
        "button_primary": "#244029",
        "button_primary_active": "#2d4f33",
        "input_bg": "#0b0b0b",
        "status_default": "#64748b",
        "status_warning": "#d6b36d",
        "status_success": "#8fd68f",
    }

    RESOLUTION_PRESETS = {
        "1920x1080 (Full HD)": (1920, 1080),
        "2560x1440 (2K QHD)": (2560, 1440),
        "3840x2160 (4K UHD)": (3840, 2160),
        "1366x768 (HD)": (1366, 768),
        "1280x720 (720p)": (1280, 720),
        "Auto-detect": None,
        "Custom": None,
    }
    MOOD_OPTIONS = [
        ("good", "Good"),
        ("neutral", "Neutral"),
        ("low", "Low"),
    ]

    def __init__(self, force_today: bool = False):
        self.root = tk.Tk()
        self.root.title("Life Calendar Daily Companion")
        self.root.minsize(700, 820)
        self.root.configure(bg=self.COLORS["bg_primary"])
        self.root.resizable(True, True)

        self.force_today = force_today
        self.config_file = os.path.join(BASE_DIR, "life_calendar_config.json")
        self.checkin_store = DailyCheckinStore(BASE_DIR)
        self.current_view = "today"
        self._normalizing_note = False
        self._note_update_job: str | None = None
        self._wallpaper_task_running = False
        self.automation_warning = ""
        self.save_settings_button: tk.Button | None = None
        self.preview_button: tk.Button | None = None
        self.refresh_button: tk.Button | None = None

        self.load_config()
        self.create_ui()
        self.refresh_today_dashboard()
        self.show_view("today" if config_has_profile(self.config) else "settings")
        if self.force_today and config_has_profile(self.config):
            self.show_view("today")

        if self.checkin_store.warning_message:
            self.set_status(self.checkin_store.warning_message, warning=True)

        self.root.bind("<Return>", self.on_enter_pressed)
        self.root.bind("<Escape>", lambda _event: self.root.quit())

    def load_config(self) -> None:
        """Load config with migration to the current shape."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as file_handle:
                    loaded = json.load(file_handle)
                self.config = merge_config(loaded)
            else:
                self.config = merge_config()
        except (json.JSONDecodeError, OSError):
            self.config = merge_config()

    def save_config(self) -> bool:
        """Persist the migrated config and keep a simple backup."""
        try:
            if os.path.exists(self.config_file):
                shutil.copy(self.config_file, self.config_file + ".bak")
            with open(self.config_file, "w", encoding="utf-8") as file_handle:
                json.dump(self.config, file_handle, indent=2)
            return True
        except OSError as exc:
            messagebox.showerror("Error", f"Failed to save config: {exc}")
            return False

    def create_ui(self) -> None:
        """Create the dashboard and settings views."""
        title = tk.Label(
            self.root,
            text="Life Calendar",
            font=("Arial", 28, "bold"),
            bg=self.COLORS["bg_primary"],
            fg=self.COLORS["text_primary"],
        )
        title.pack(pady=(18, 6))

        subtitle = tk.Label(
            self.root,
            text="A daily reminder that time is finite.",
            font=("Arial", 11),
            bg=self.COLORS["bg_primary"],
            fg=self.COLORS["text_secondary"],
        )
        subtitle.pack(pady=(0, 18))

        nav_frame = tk.Frame(self.root, bg=self.COLORS["bg_nav"])
        nav_frame.pack(fill="x", padx=28)

        self.today_nav_btn = tk.Button(
            nav_frame,
            text="Today",
            font=("Arial", 10, "bold"),
            bg=self.COLORS["bg_nav_active"],
            fg="#dff4e0",
            activebackground="#243526",
            relief="flat",
            bd=0,
            padx=16,
            pady=9,
            cursor="hand2",
            command=lambda: self.show_view("today"),
        )
        self.today_nav_btn.pack(side="left", padx=(0, 10))

        self.settings_nav_btn = tk.Button(
            nav_frame,
            text="Settings",
            font=("Arial", 10),
            bg=self.COLORS["bg_nav_inactive"],
            fg=self.COLORS["text_secondary"],
            activebackground="#1d1d1d",
            relief="flat",
            bd=0,
            padx=16,
            pady=9,
            cursor="hand2",
            command=lambda: self.show_view("settings"),
        )
        self.settings_nav_btn.pack(side="left")

        self.content_frame = tk.Frame(self.root, bg=self.COLORS["bg_primary"])
        self.content_frame.pack(fill="both", expand=True, padx=28, pady=18)

        self.today_view = tk.Frame(self.content_frame, bg=self.COLORS["bg_primary"])
        self.settings_view = tk.Frame(self.content_frame, bg=self.COLORS["bg_primary"])

        self.create_today_view()
        self.create_settings_view()

        self.status_label = tk.Label(
            self.root,
            text="Complete setup once, then come back daily.",
            font=("Arial", 9),
            bg=self.COLORS["bg_primary"],
            fg=self.COLORS["text_secondary"],
        )
        self.status_label.pack(pady=(0, 12))

    def create_today_view(self) -> None:
        """Create the Today dashboard."""
        card = tk.Frame(self.today_view, bg=self.COLORS["bg_secondary"])
        card.pack(fill="both", expand=True)

        tk.Label(
            card,
            text="TODAY",
            font=("Arial", 24, "bold"),
            bg=self.COLORS["bg_secondary"],
            fg=self.COLORS["text_primary"],
        ).pack(anchor="w", padx=28, pady=(24, 6))

        self.today_date_label = tk.Label(
            card,
            text="",
            font=("Arial", 11),
            bg=self.COLORS["bg_secondary"],
            fg=self.COLORS["text_secondary"],
        )
        self.today_date_label.pack(anchor="w", padx=28)

        self.today_primary_label = tk.Label(
            card,
            text="Day 0 / 0",
            font=("Arial", 22, "bold"),
            bg=self.COLORS["bg_secondary"],
            fg=self.COLORS["text_primary"],
        )
        self.today_primary_label.pack(anchor="w", padx=28, pady=(26, 4))

        self.today_stat_one_label = tk.Label(
            card,
            text="",
            font=("Arial", 12),
            bg=self.COLORS["bg_secondary"],
            fg=self.COLORS["text_primary"],
        )
        self.today_stat_one_label.pack(anchor="w", padx=28, pady=(4, 2))

        self.today_stat_two_label = tk.Label(
            card,
            text="",
            font=("Arial", 12),
            bg=self.COLORS["bg_secondary"],
            fg=self.COLORS["text_soft"],
        )
        self.today_stat_two_label.pack(anchor="w", padx=28, pady=(2, 16))

        self.today_streak_label = tk.Label(
            card,
            text="",
            font=("Arial", 11, "bold"),
            bg=self.COLORS["bg_secondary"],
            fg=self.COLORS["accent_success_soft"],
        )
        self.today_streak_label.pack(anchor="w", padx=28)

        self.today_emotional_label = tk.Label(
            card,
            text="",
            font=("Arial", 12),
            bg=self.COLORS["bg_secondary"],
            fg=self.COLORS["text_info"],
            wraplength=560,
            justify="left",
        )
        self.today_emotional_label.pack(anchor="w", padx=28, pady=(14, 12))

        self.today_checkin_state_label = tk.Label(
            card,
            text="",
            font=("Arial", 10),
            bg=self.COLORS["bg_secondary"],
            fg=self.COLORS["text_hint"],
        )
        self.today_checkin_state_label.pack(anchor="w", padx=28, pady=(0, 18))

        mood_frame = tk.Frame(card, bg=self.COLORS["bg_secondary"])
        mood_frame.pack(anchor="w", padx=28, pady=(0, 12))

        tk.Label(
            mood_frame,
            text="Mood",
            font=("Arial", 10, "bold"),
            bg=self.COLORS["bg_secondary"],
            fg=self.COLORS["text_primary"],
        ).pack(anchor="w", pady=(0, 8))

        self.mood_var = tk.StringVar(value="neutral")
        buttons_frame = tk.Frame(mood_frame, bg=self.COLORS["bg_secondary"])
        buttons_frame.pack(anchor="w")
        for mood_key, mood_label in self.MOOD_OPTIONS:
            tk.Radiobutton(
                buttons_frame,
                text=mood_label,
                variable=self.mood_var,
                value=mood_key,
                indicatoron=0,
                font=("Arial", 10),
                selectcolor="#263626",
                bg="#1d1d1d",
                fg="#dedede",
                activebackground="#252525",
                activeforeground="#f2f2f2",
                relief="flat",
                bd=0,
                padx=16,
                pady=8,
                width=10,
                cursor="hand2",
            ).pack(side="left", padx=(0, 10))

        note_frame = tk.Frame(card, bg=self.COLORS["bg_secondary"])
        note_frame.pack(fill="x", padx=28, pady=(8, 0))

        tk.Label(
            note_frame,
            text="What did you do today?",
            font=("Arial", 10, "bold"),
            bg=self.COLORS["bg_secondary"],
            fg=self.COLORS["text_primary"],
        ).pack(anchor="w", pady=(0, 8))

        self.note_var = tk.StringVar()
        self.note_var.trace_add("write", self.on_note_change)
        self.note_entry = tk.Entry(
            note_frame,
            textvariable=self.note_var,
            font=("Arial", 11),
            bg=self.COLORS["input_bg"],
            fg=self.COLORS["text_primary"],
            relief="flat",
            bd=6,
            insertbackground=self.COLORS["text_primary"],
        )
        self.note_entry.pack(fill="x")

        self.note_counter_label = tk.Label(
            note_frame,
            text=f"0/{MAX_NOTE_LENGTH}",
            font=("Arial", 9),
            bg=self.COLORS["bg_secondary"],
            fg=self.COLORS["text_note_counter"],
        )
        self.note_counter_label.pack(anchor="e", pady=(6, 0))

        action_frame = tk.Frame(card, bg=self.COLORS["bg_secondary"])
        action_frame.pack(anchor="w", padx=28, pady=(24, 28))

        self.checkin_button = tk.Button(
            action_frame,
            text="Check in for today",
            font=("Arial", 12, "bold"),
            bg=self.COLORS["button_primary"],
            fg=self.COLORS["text_primary"],
            activebackground=self.COLORS["button_primary_active"],
            relief="flat",
            bd=0,
            padx=24,
            pady=12,
            cursor="hand2",
            command=self.submit_checkin,
        )
        self.checkin_button.pack(side="left", padx=(0, 10))

        self.refresh_button = tk.Button(
            action_frame,
            text="Refresh wallpaper now",
            font=("Arial", 10),
            bg=self.COLORS["button_secondary"],
            fg=self.COLORS["text_soft"],
            activebackground=self.COLORS["button_secondary_active"],
            relief="flat",
            bd=0,
            padx=18,
            pady=12,
            cursor="hand2",
            command=self.refresh_wallpaper_now,
        )
        self.refresh_button.pack(side="left", padx=(0, 10))

        tk.Button(
            action_frame,
            text="Open Settings",
            font=("Arial", 10),
            bg=self.COLORS["button_secondary"],
            fg=self.COLORS["text_soft"],
            activebackground=self.COLORS["button_secondary_active"],
            relief="flat",
            bd=0,
            padx=18,
            pady=12,
            cursor="hand2",
            command=lambda: self.show_view("settings"),
        ).pack(side="left")

    def create_settings_view(self) -> None:
        """Create the settings panel."""
        card = tk.Frame(self.settings_view, bg="#101010")
        card.pack(fill="both", expand=True)

        tk.Label(
            card,
            text="SETTINGS",
            font=("Arial", 22, "bold"),
            bg="#101010",
            fg="#f2f2f2",
        ).pack(anchor="w", padx=28, pady=(24, 4))

        tk.Label(
            card,
            text="Configure the wallpaper once, then let the daily loop pull you back in.",
            font=("Arial", 10),
            bg="#101010",
            fg="#949494",
        ).pack(anchor="w", padx=28, pady=(0, 18))

        mode_frame = tk.Frame(card, bg="#101010")
        mode_frame.pack(fill="x", padx=28, pady=(0, 14))

        tk.Label(
            mode_frame,
            text="Calendar Mode",
            bg="#101010",
            fg="#9a9a9a",
            font=("Arial", 10),
        ).pack(side="left", padx=(0, 10))

        self.mode_var = tk.StringVar(value=self.config.get("mode", "life"))
        self.mode_dropdown = ttk.Combobox(
            mode_frame,
            textvariable=self.mode_var,
            values=["life", "year", "goal"],
            state="readonly",
            width=15,
        )
        self.mode_dropdown.pack(side="left")
        self.mode_dropdown.bind("<<ComboboxSelected>>", self.on_mode_change)

        self.settings_body = tk.Frame(card, bg="#141414")
        self.settings_body.pack(fill="both", expand=True, padx=28, pady=(0, 14))

        self.mode_settings_container = tk.Frame(self.settings_body, bg="#141414")
        self.mode_settings_container.pack(fill="x", padx=18, pady=(14, 0))

        self.create_life_settings()
        self.create_year_settings()
        self.create_goal_settings()

        self.res_frame = tk.Frame(self.settings_body, bg="#141414")
        self.res_frame.pack(fill="x", padx=18, pady=(16, 0))
        self.create_resolution_settings()

        self.automation_frame = tk.Frame(self.settings_body, bg="#141414")
        self.automation_frame.pack(fill="x", padx=18, pady=(18, 0))
        self.create_automation_settings()

        actions = tk.Frame(card, bg="#101010")
        actions.pack(fill="x", padx=28, pady=(0, 26))

        self.save_settings_button = tk.Button(
            actions,
            text="Save settings & activate",
            font=("Arial", 11, "bold"),
            bg="#2e4c35",
            fg=self.COLORS["text_primary"],
            activebackground="#386040",
            relief="flat",
            bd=0,
            padx=22,
            pady=12,
            cursor="hand2",
            command=self.save_settings_and_activate,
        )
        self.save_settings_button.pack(side="left", padx=(0, 10))

        self.preview_button = tk.Button(
            actions,
            text="Preview",
            font=("Arial", 10),
            bg=self.COLORS["button_secondary"],
            fg=self.COLORS["text_soft"],
            activebackground=self.COLORS["button_secondary_active"],
            relief="flat",
            bd=0,
            padx=18,
            pady=12,
            cursor="hand2",
            command=self.preview_wallpaper,
        )
        self.preview_button.pack(side="left", padx=(0, 10))

        self.retry_automation_button = tk.Button(
            actions,
            text="Retry automation",
            font=("Arial", 10),
            bg="#181818",
            fg="#d5d5d5",
            activebackground="#202020",
            relief="flat",
            bd=0,
            padx=18,
            pady=12,
            cursor="hand2",
            command=self.retry_automation,
        )
        self.retry_automation_button.pack(side="left", padx=(0, 10))

        tk.Button(
            actions,
            text="Reset",
            font=("Arial", 10),
            bg="#181818",
            fg="#d5d5d5",
            activebackground="#202020",
            relief="flat",
            bd=0,
            padx=18,
            pady=12,
            cursor="hand2",
            command=self.reset_defaults,
        ).pack(side="left", padx=(0, 10))

        tk.Button(
            actions,
            text="Help",
            font=("Arial", 10),
            bg="#181818",
            fg="#d5d5d5",
            activebackground="#202020",
            relief="flat",
            bd=0,
            padx=18,
            pady=12,
            cursor="hand2",
            command=self.show_help,
        ).pack(side="left")

        self.on_mode_change()
        self.update_automation_status()

    def create_life_settings(self) -> None:
        self.life_frame = tk.Frame(self.mode_settings_container, bg="#141414")

        tk.Label(
            self.life_frame,
            text="Date of Birth",
            font=("Arial", 10),
            bg="#141414",
            fg="#9a9a9a",
        ).pack(anchor="w", pady=(0, 6))

        self.dob_entry = tk.Entry(
            self.life_frame,
            font=("Arial", 11),
            bg="#0b0b0b",
            fg="#f2f2f2",
            relief="flat",
            bd=6,
            insertbackground="#f2f2f2",
        )
        self.dob_entry.pack(fill="x")
        self.dob_entry.insert(0, self.config.get("dob", ""))

        tk.Label(
            self.life_frame,
            text="Format: YYYY-MM-DD",
            font=("Arial", 8),
            bg="#141414",
            fg="#64748b",
        ).pack(anchor="w", pady=(4, 12))

        tk.Label(
            self.life_frame,
            text="Expected Lifespan (Years)",
            font=("Arial", 10),
            bg="#141414",
            fg="#9a9a9a",
        ).pack(anchor="w", pady=(0, 6))

        self.lifespan_entry = tk.Entry(
            self.life_frame,
            font=("Arial", 11),
            bg="#0b0b0b",
            fg="#f2f2f2",
            relief="flat",
            bd=6,
            insertbackground="#f2f2f2",
        )
        self.lifespan_entry.pack(fill="x")
        self.lifespan_entry.insert(0, str(self.config.get("lifespan", 90)))

        tk.Label(
            self.life_frame,
            text="Between 1 and 150 years",
            font=("Arial", 8),
            bg="#141414",
            fg="#64748b",
        ).pack(anchor="w", pady=(4, 0))

    def create_year_settings(self) -> None:
        self.year_frame = tk.Frame(self.mode_settings_container, bg="#141414")
        today = date.today()

        tk.Label(
            self.year_frame,
            text="Year Progress",
            font=("Arial", 12, "bold"),
            bg="#141414",
            fg="#f2f2f2",
        ).pack(anchor="w", pady=(0, 10))

        tk.Label(
            self.year_frame,
            text="No setup needed. This mode always uses the current system date.",
            font=("Arial", 10),
            bg="#141414",
            fg="#9a9a9a",
            wraplength=520,
            justify="left",
        ).pack(anchor="w")

        tk.Label(
            self.year_frame,
            text=f"Today: {today.strftime('%B %d, %Y')} (Day {today.timetuple().tm_yday})",
            font=("Arial", 10),
            bg="#141414",
            fg="#d0d0d0",
        ).pack(anchor="w", pady=(10, 0))

    def create_goal_settings(self) -> None:
        self.goal_frame = tk.Frame(self.mode_settings_container, bg="#141414")

        tk.Label(
            self.goal_frame,
            text="Goal Title",
            font=("Arial", 10),
            bg="#141414",
            fg="#9a9a9a",
        ).pack(anchor="w", pady=(0, 6))

        self.goal_title_entry = tk.Entry(
            self.goal_frame,
            font=("Arial", 11),
            bg="#0b0b0b",
            fg="#f2f2f2",
            relief="flat",
            bd=6,
            insertbackground="#f2f2f2",
        )
        self.goal_title_entry.pack(fill="x")
        self.goal_title_entry.insert(0, self.config.get("goal_title", ""))

        tk.Label(
            self.goal_frame,
            text="Subtitle (optional)",
            font=("Arial", 9),
            bg="#141414",
            fg="#9a9a9a",
        ).pack(anchor="w", pady=(10, 6))

        self.goal_subtitle_entry = tk.Entry(
            self.goal_frame,
            font=("Arial", 10),
            bg="#0b0b0b",
            fg="#d6d6d6",
            relief="flat",
            bd=6,
            insertbackground="#d6d6d6",
        )
        self.goal_subtitle_entry.pack(fill="x")
        self.goal_subtitle_entry.insert(0, self.config.get("goal_subtitle", ""))

        tk.Label(
            self.goal_frame,
            text="Goal Start Date",
            font=("Arial", 10),
            bg="#141414",
            fg="#9a9a9a",
        ).pack(anchor="w", pady=(14, 6))

        self.goal_start_entry = tk.Entry(
            self.goal_frame,
            font=("Arial", 11),
            bg="#0b0b0b",
            fg="#f2f2f2",
            relief="flat",
            bd=6,
            insertbackground="#f2f2f2",
        )
        self.goal_start_entry.pack(fill="x")
        self.goal_start_entry.insert(0, self.config.get("goal_start", ""))

        tk.Label(
            self.goal_frame,
            text="Goal End Date",
            font=("Arial", 10),
            bg="#141414",
            fg="#9a9a9a",
        ).pack(anchor="w", pady=(14, 6))

        self.goal_end_entry = tk.Entry(
            self.goal_frame,
            font=("Arial", 11),
            bg="#0b0b0b",
            fg="#f2f2f2",
            relief="flat",
            bd=6,
            insertbackground="#f2f2f2",
        )
        self.goal_end_entry.pack(fill="x")
        self.goal_end_entry.insert(0, self.config.get("goal_end", ""))

        tk.Label(
            self.goal_frame,
            text="Format: YYYY-MM-DD",
            font=("Arial", 8),
            bg="#141414",
            fg="#64748b",
        ).pack(anchor="w", pady=(4, 0))

    def create_resolution_settings(self) -> None:
        tk.Label(
            self.res_frame,
            text="Screen Resolution",
            font=("Arial", 10),
            bg="#141414",
            fg="#9a9a9a",
        ).pack(anchor="w")

        preset_frame = tk.Frame(self.res_frame, bg="#141414")
        preset_frame.pack(anchor="w", pady=(6, 8))

        config_width = self.config.get("resolution_width", 1920)
        config_height = self.config.get("resolution_height", 1080)
        current_preset = "Custom"
        for preset_name, preset_value in self.RESOLUTION_PRESETS.items():
            if preset_value == (config_width, config_height):
                current_preset = preset_name
                break

        self.preset_var = tk.StringVar(value=current_preset)
        self.preset_dropdown = ttk.Combobox(
            preset_frame,
            textvariable=self.preset_var,
            values=list(self.RESOLUTION_PRESETS.keys()),
            state="readonly",
            width=20,
        )
        self.preset_dropdown.pack(side="left")
        self.preset_dropdown.bind("<<ComboboxSelected>>", self.on_preset_change)

        custom_frame = tk.Frame(self.res_frame, bg="#141414")
        custom_frame.pack(anchor="w")

        self.width_entry = tk.Entry(
            custom_frame,
            font=("Arial", 11),
            bg="#0b0b0b",
            fg="#f2f2f2",
            width=8,
            relief="flat",
            bd=6,
            insertbackground="#f2f2f2",
        )
        self.width_entry.pack(side="left")
        self.width_entry.insert(0, str(config_width))

        tk.Label(
            custom_frame,
            text="x",
            bg="#141414",
            fg="#9a9a9a",
            font=("Arial", 11),
        ).pack(side="left", padx=6)

        self.height_entry = tk.Entry(
            custom_frame,
            font=("Arial", 11),
            bg="#0b0b0b",
            fg="#f2f2f2",
            width=8,
            relief="flat",
            bd=6,
            insertbackground="#f2f2f2",
        )
        self.height_entry.pack(side="left")
        self.height_entry.insert(0, str(config_height))

        tk.Label(
            self.res_frame,
            text="Minimum: 800x600",
            font=("Arial", 8),
            bg="#141414",
            fg="#64748b",
        ).pack(anchor="w", pady=(6, 0))

    def create_automation_settings(self) -> None:
        tk.Label(
            self.automation_frame,
            text="Automation",
            font=("Arial", 10, "bold"),
            bg="#141414",
            fg="#f2f2f2",
        ).pack(anchor="w")

        tk.Label(
            self.automation_frame,
            text="Windows-first: schedule nightly refreshes and a startup reminder without manual setup.",
            font=("Arial", 9),
            bg="#141414",
            fg="#8f8f8f",
            wraplength=520,
            justify="left",
        ).pack(anchor="w", pady=(6, 10))

        automation = self.config.get("automation", {})
        self.startup_enabled_var = tk.BooleanVar(value=automation.get("startup_enabled", True))
        self.wallpaper_refresh_enabled_var = tk.BooleanVar(
            value=automation.get("wallpaper_refresh_enabled", True)
        )

        self.wallpaper_task_checkbox = tk.Checkbutton(
            self.automation_frame,
            text="Refresh wallpaper nightly and after unlock",
            variable=self.wallpaper_refresh_enabled_var,
            bg="#141414",
            fg="#d6d6d6",
            activebackground="#141414",
            activeforeground="#f2f2f2",
            selectcolor="#0b0b0b",
            relief="flat",
            bd=0,
        )
        self.wallpaper_task_checkbox.pack(anchor="w")

        self.startup_checkbox = tk.Checkbutton(
            self.automation_frame,
            text="Open the app at login only if you have not checked in yet",
            variable=self.startup_enabled_var,
            bg="#141414",
            fg="#d6d6d6",
            activebackground="#141414",
            activeforeground="#f2f2f2",
            selectcolor="#0b0b0b",
            relief="flat",
            bd=0,
        )
        self.startup_checkbox.pack(anchor="w", pady=(4, 0))

        self.automation_status_label = tk.Label(
            self.automation_frame,
            text="",
            font=("Arial", 9),
            bg="#141414",
            fg="#6f7f96",
            wraplength=520,
            justify="left",
        )
        self.automation_status_label.pack(anchor="w", pady=(10, 0))

        if platform.system() != "Windows":
            self.wallpaper_task_checkbox.config(state="disabled")
            self.startup_checkbox.config(state="disabled")

    def on_mode_change(self, _event: Any = None) -> None:
        """Switch the visible mode-specific settings."""
        for frame in (self.life_frame, self.year_frame, self.goal_frame):
            frame.pack_forget()

        mode = self.mode_var.get()
        if mode == "life":
            self.life_frame.pack(fill="x")
        elif mode == "goal":
            self.goal_frame.pack(fill="x")
        else:
            self.year_frame.pack(fill="x")

    def on_preset_change(self, _event: Any = None) -> None:
        """Update resolution inputs when the preset changes."""
        preset = self.preset_var.get()
        if preset == "Auto-detect":
            width, height = get_screen_resolution()
            if messagebox.askyesno(
                "Auto-detect Resolution",
                f"Detected {width}x{height}. Use this resolution?",
            ):
                self.width_entry.delete(0, tk.END)
                self.width_entry.insert(0, str(width))
                self.height_entry.delete(0, tk.END)
                self.height_entry.insert(0, str(height))
            else:
                self.preset_var.set("Custom")
            return

        if preset == "Custom":
            return

        resolution = self.RESOLUTION_PRESETS.get(preset)
        if resolution is None:
            return

        width, height = resolution
        self.width_entry.delete(0, tk.END)
        self.width_entry.insert(0, str(width))
        self.height_entry.delete(0, tk.END)
        self.height_entry.insert(0, str(height))

    def on_note_change(self, *_args: Any) -> None:
        """Debounce note normalization to avoid work on every keystroke."""
        if self._normalizing_note:
            return

        if self._note_update_job is not None:
            self.root.after_cancel(self._note_update_job)
        self._note_update_job = self.root.after(75, self._apply_note_normalization)

    def _apply_note_normalization(self) -> None:
        """Keep the daily note to one line and max length from config."""
        self._note_update_job = None

        max_length = self.config.get("max_note_length", MAX_NOTE_LENGTH)
        raw_note = self.note_var.get().replace("\r", " ").replace("\n", " ")
        if len(raw_note) > max_length:
            raw_note = raw_note[:max_length]

        if raw_note != self.note_var.get():
            self._normalizing_note = True
            self.note_var.set(raw_note)
            self._normalizing_note = False

        self.note_counter_label.config(text=f"{len(self.note_var.get())}/{max_length}")

    def show_view(self, view_name: str) -> None:
        """Show the selected view."""
        self.current_view = view_name
        self.today_view.pack_forget()
        self.settings_view.pack_forget()

        if view_name == "today":
            self.today_view.pack(fill="both", expand=True)
        else:
            self.settings_view.pack(fill="both", expand=True)

        self.today_nav_btn.config(
            bg=self.COLORS["bg_nav_active"] if view_name == "today" else self.COLORS["bg_nav_inactive"],
            fg="#dff4e0" if view_name == "today" else "#c9c9c9",
            font=("Arial", 10, "bold") if view_name == "today" else ("Arial", 10),
        )
        self.settings_nav_btn.config(
            bg=self.COLORS["bg_nav_active_settings"] if view_name == "settings" else self.COLORS["bg_nav_inactive"],
            fg="#dbe7f8" if view_name == "settings" else "#c9c9c9",
            font=("Arial", 10, "bold") if view_name == "settings" else ("Arial", 10),
        )

    def set_status(self, message: str, warning: bool = False, success: bool = False) -> None:
        """Update the status line."""
        color = self.COLORS["status_default"]
        if warning:
            color = self.COLORS["status_warning"]
        elif success:
            color = self.COLORS["status_success"]
        self.status_label.config(text=message, fg=color)

    def _set_wallpaper_busy(self, busy: bool) -> None:
        """Disable wallpaper action buttons while a generation task is running."""
        self._wallpaper_task_running = busy
        state = "disabled" if busy else "normal"
        for button in (self.save_settings_button, self.preview_button, self.refresh_button):
            if button is not None:
                button.config(state=state)

    def _run_wallpaper_task(
        self,
        status_message: str,
        worker: Callable[[], Any],
        on_done: Callable[[Any, Exception | None], None],
    ) -> None:
        """Run wallpaper generation in a worker thread to keep UI responsive."""
        if self._wallpaper_task_running:
            self.set_status("A wallpaper task is already running. Please wait.", warning=True)
            return

        self._set_wallpaper_busy(True)
        self.set_status(status_message)

        def run_worker() -> None:
            result: Any = None
            error: Exception | None = None
            try:
                result = worker()
            except Exception as exc:  # noqa: BLE001 - bubble to main thread handler
                error = exc
            self.root.after(0, lambda: self._finish_wallpaper_task(result, error, on_done))

        threading.Thread(target=run_worker, daemon=True).start()

    def _finish_wallpaper_task(
        self,
        result: Any,
        error: Exception | None,
        on_done: Callable[[Any, Exception | None], None],
    ) -> None:
        """Finalize async wallpaper task on the main thread."""
        self._set_wallpaper_busy(False)
        on_done(result, error)

    def update_automation_status(self) -> None:
        """Show current automation messaging."""
        if platform.system() != "Windows":
            self.automation_status_label.config(
                text="Startup reminder and one-click automation stay Windows-first in this version.",
                fg="#7f8aa0",
            )
            self.retry_automation_button.config(state="disabled")
            return

        if self.automation_warning:
            self.automation_status_label.config(text=self.automation_warning, fg="#d6b36d")
        else:
            self.automation_status_label.config(
                text="Automation will be applied when you save settings.",
                fg="#7f8aa0",
            )

    def refresh_today_dashboard(self) -> None:
        """Refresh the daily dashboard from saved config and check-ins."""
        today = date.today()
        self.today_date_label.config(text=today.strftime("%A, %B %d, %Y"))

        if not config_has_profile(self.config):
            self.today_primary_label.config(text="Complete setup in Settings")
            self.today_stat_one_label.config(text="Save a valid profile to unlock the daily loop.")
            self.today_stat_two_label.config(text="")
            self.today_streak_label.config(text="Streak: 0 days")
            self.today_emotional_label.config(text="The reminder gets stronger once your profile is set.")
            self.today_checkin_state_label.config(text="Check-in is unavailable until setup is complete.")
            self.checkin_button.config(state="disabled")
            return

        metrics = get_today_metrics(self.config, today)
        entry = self.checkin_store.get_entry(today)
        streak = self.checkin_store.current_streak(today)

        self.today_primary_label.config(text=metrics.primary_line)
        self.today_stat_one_label.config(text=metrics.secondary_lines[0])
        self.today_stat_two_label.config(text=metrics.secondary_lines[1])
        self.today_streak_label.config(text=f"You showed up {streak} day{'s' if streak != 1 else ''} in a row.")
        self.today_emotional_label.config(text=metrics.emotional_line)
        self.checkin_button.config(state="normal")

        if entry:
            self.mood_var.set(entry.get("mood", "neutral"))
            self.note_var.set(entry.get("note", ""))
            timestamp = entry.get("updated_at", "")
            time_label = self._format_timestamp(timestamp)
            self.today_checkin_state_label.config(text=f"Checked in today{time_label}.")
            self.checkin_button.config(text="Update today's check-in")
        else:
            self.mood_var.set("neutral")
            self.note_var.set("")
            self.today_checkin_state_label.config(text="Not checked in yet.")
            self.checkin_button.config(text="Check in for today")

    def _format_timestamp(self, timestamp: str) -> str:
        """Format an ISO timestamp for UI display."""
        if not timestamp:
            return ""
        try:
            parsed = datetime.fromisoformat(timestamp)
            return f" at {parsed.strftime('%I:%M %p').lstrip('0')}"
        except ValueError:
            return ""

    def on_enter_pressed(self, _event: Any) -> None:
        """Handle Enter based on the visible view."""
        if self.current_view == "today":
            self.submit_checkin()
        else:
            self.save_settings_and_activate()

    def _validate_and_sync_life_mode(self) -> bool:
        """Validate and sync life mode settings from UI to config."""
        dob = self.dob_entry.get().strip()
        if not dob:
            messagebox.showerror("Validation Error", "Date of birth is required.")
            return False
        if safe_date(dob) is None:
            messagebox.showerror("Invalid Date", "Date of birth must use YYYY-MM-DD.")
            return False

        lifespan_str = self.lifespan_entry.get().strip()
        if not lifespan_str.isdigit():
            messagebox.showerror("Validation Error", "Lifespan must be a number.")
            return False

        lifespan = int(lifespan_str)
        if lifespan < 1 or lifespan > 150:
            messagebox.showerror("Validation Error", "Lifespan must be between 1 and 150.")
            return False

        self.config["dob"] = dob
        self.config["lifespan"] = lifespan
        return True

    def _validate_and_sync_goal_mode(self) -> bool:
        """Validate and sync goal mode settings from UI to config."""
        title = self.goal_title_entry.get().strip()
        if not title:
            messagebox.showerror("Validation Error", "Goal title is required.")
            return False

        start = self.goal_start_entry.get().strip()
        end = self.goal_end_entry.get().strip()
        start_date = safe_date(start)
        end_date = safe_date(end)

        if start_date is None or end_date is None:
            messagebox.showerror("Invalid Date", "Goal dates must use YYYY-MM-DD.")
            return False
        if end_date <= start_date:
            messagebox.showerror("Invalid Dates", "Goal end must be after goal start.")
            return False

        self.config["goal_title"] = title
        self.config["goal_subtitle"] = self.goal_subtitle_entry.get().strip()
        self.config["goal_start"] = start
        self.config["goal_end"] = end
        return True

    def _validate_and_sync_resolution(self) -> bool:
        """Validate and sync resolution settings from UI to config."""
        width = safe_int(self.width_entry.get(), 1920)
        height = safe_int(self.height_entry.get(), 1080)
        if width < 800 or height < 600:
            messagebox.showerror("Resolution Error", "Resolution must be at least 800x600.")
            return False
        if width > 7680 or height > 4320:
            messagebox.showerror("Resolution Error", "Resolution must be at most 7680x4320.")
            return False

        self.config["resolution_width"] = width
        self.config["resolution_height"] = height
        return True

    def _sync_automation_settings(self) -> None:
        """Sync automation checkbox settings to config."""
        self.config["automation"] = {
            "startup_enabled": bool(self.startup_enabled_var.get()),
            "wallpaper_refresh_enabled": bool(self.wallpaper_refresh_enabled_var.get()),
        }

    def _sync_config_from_ui(self) -> bool:
        """Validate settings inputs and sync them into the config.

        Orchestrates validation and syncing of all UI inputs to config dictionary.
        Returns True if all validation passes, False otherwise.
        """
        mode = self.mode_var.get()
        self.config["mode"] = mode

        # Validate mode-specific settings
        if mode == "life":
            if not self._validate_and_sync_life_mode():
                return False
        elif mode == "goal":
            if not self._validate_and_sync_goal_mode():
                return False

        # Validate and sync resolution
        if not self._validate_and_sync_resolution():
            return False

        # Sync automation settings
        self._sync_automation_settings()

        # Finalize config with merge
        self.config = merge_config(self.config)
        return True

    def save_settings_and_activate(self) -> None:
        """Save settings, generate wallpaper, and apply automation."""
        if not self._sync_config_from_ui():
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
            self.set_status(str(error), warning=True)
            return

        if not bool(result):
            messagebox.showerror("Error", "Failed to generate or set the wallpaper. Check wallpaper.log.")
            self.set_status("Wallpaper generation failed.", warning=True)
            return

        self.apply_windows_automation(show_success=False)
        self.load_config()
        self.refresh_today_dashboard()
        self.show_view("today")
        self.set_status("Setup complete. Your daily companion is active.", success=True)
        messagebox.showinfo(
            "Setup Complete",
            "Wallpaper updated successfully.\n\nYour Today dashboard is ready for daily check-ins.",
        )

    def apply_windows_automation(self, show_success: bool = True) -> bool:
        """Apply Windows automation preferences without making failures fatal."""
        if platform.system() != "Windows":
            self.automation_warning = ""
            self.update_automation_status()
            return True

        success, errors = sync_windows_tasks(self.config, BASE_DIR)
        if success:
            self.automation_warning = ""
            self.update_automation_status()
            if show_success:
                self.set_status("Windows automation is active.", success=True)
            return True

        # Format errors for display
        error_details = "\n".join(f"• {error}" for error in errors)
        self.automation_warning = (
            "Automation setup encountered issues. "
            "If you see access denied, run Life Calendar as Administrator and retry."
            f"\n{error_details}"
        )
        self.update_automation_status()
        self.set_status("Automation setup failed - check retry button.", warning=True)

        # Show detailed error dialog to user
        messagebox.showwarning(
            "Automation Setup Failed",
            f"Could not set up Windows automation:\n\n{error_details}\n\n"
            "You can retry from Settings or run as Administrator for full permissions.",
        )
        return False

    def retry_automation(self) -> None:
        """Retry task registration from Settings."""
        if not self._sync_config_from_ui():
            return
        if not self.save_config():
            self.set_status("Unable to save config. Automation retry cancelled.", warning=True)
            return
        self.apply_windows_automation(show_success=True)

    def preview_wallpaper(self) -> None:
        """Generate a preview of the wallpaper without setting it."""
        if not self._sync_config_from_ui():
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
            self.set_status(str(error), warning=True)
            return

        success, message, wallpaper_path = result
        if success:
            from PIL import Image

            Image.open(wallpaper_path).show()
            self.set_status("Preview opened.", success=True)
            return

        messagebox.showerror("Error", message)
        self.set_status(message, warning=True)

    def refresh_wallpaper_now(self) -> None:
        """Refresh the wallpaper immediately from the saved config."""
        if not config_has_profile(self.config):
            self.set_status("Finish setup in Settings before refreshing the wallpaper.", warning=True)
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
            self.set_status(str(error), warning=True)
            return

        if bool(result):
            self.set_status("Wallpaper refreshed.", success=True)
            return

        self.set_status("Wallpaper refresh failed. Check wallpaper.log.", warning=True)

    def submit_checkin(self) -> None:
        """Save or update today's daily check-in."""
        if not config_has_profile(self.config):
            self.set_status("Finish setup before checking in.", warning=True)
            self.show_view("settings")
            return

        note = self.note_var.get()
        mood = self.mood_var.get()
        if mood not in VALID_MOODS:
            mood = "neutral"

        max_note_length = int(self.config.get("max_note_length", MAX_NOTE_LENGTH))
        result = self.checkin_store.check_in(mood, note, max_note_length=max_note_length)
        self.refresh_today_dashboard()
        if result.updated_existing:
            self.set_status(
                f"Today's check-in was updated. Current streak: {result.streak} day{'s' if result.streak != 1 else ''}.",
                success=True,
            )
        else:
            self.set_status(
                f"Checked in for today. Current streak: {result.streak} day{'s' if result.streak != 1 else ''}.",
                success=True,
            )

    def reset_defaults(self) -> None:
        """Reset config to defaults and return to Settings."""
        if not messagebox.askyesno("Reset Settings", "Reset the app back to default settings?"):
            return

        self.config = merge_config()
        if not self.save_config():
            self.set_status("Failed to reset defaults because config could not be saved.", warning=True)
            return

        self.mode_var.set(self.config.get("mode", "life"))
        self.dob_entry.delete(0, tk.END)
        self.dob_entry.insert(0, self.config.get("dob", ""))
        self.lifespan_entry.delete(0, tk.END)
        self.lifespan_entry.insert(0, str(self.config.get("lifespan", 90)))
        self.goal_title_entry.delete(0, tk.END)
        self.goal_subtitle_entry.delete(0, tk.END)
        self.goal_start_entry.delete(0, tk.END)
        self.goal_end_entry.delete(0, tk.END)
        self.width_entry.delete(0, tk.END)
        self.width_entry.insert(0, str(self.config.get("resolution_width", 1920)))
        self.height_entry.delete(0, tk.END)
        self.height_entry.insert(0, str(self.config.get("resolution_height", 1080)))
        self.startup_enabled_var.set(self.config["automation"]["startup_enabled"])
        self.wallpaper_refresh_enabled_var.set(self.config["automation"]["wallpaper_refresh_enabled"])
        self.preset_var.set("1920x1080 (Full HD)")
        self.on_mode_change()
        self.refresh_today_dashboard()
        self.show_view("settings")
        self.set_status("Settings reset to defaults.", success=True)

    def show_help(self) -> None:
        """Show a short help message."""
        help_text = (
            "Life Calendar Daily Companion\n\n"
            "Today:\n"
            "- Check in once per day with a mood and one short note.\n"
            "- Watch your streak and progress update.\n\n"
            "Settings:\n"
            "- Configure life, year, or goal mode.\n"
            "- Save settings to generate the wallpaper and register Windows automation.\n\n"
            "Command modes:\n"
            "- --headless-update refreshes the wallpaper silently.\n"
            "- --startup-check opens the app only if you have not checked in yet."
        )
        messagebox.showinfo("Help", help_text)

    def run(self) -> None:
        self.root.mainloop()


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
        from auto_update import main as auto_update_main

        return auto_update_main()

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
