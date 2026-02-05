"""
Life Calendar Wallpaper Generator - GUI Application
Uses wallpaper_engine.py for all generation logic
GUI ONLY for configuration - ENGINE handles generation
Version 2.0 - Improved with better validation and UX
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime
import json
import os
import sys
import threading
from typing import Dict, Any, Optional
import shutil
import platform
import ctypes

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


# Import headless engine (safe_int is GUI-only, not imported from engine)
from wallpaper_engine import WallpaperEngine, safe_date, get_screen_resolution


# ==================== GUI HELPER FUNCTIONS ====================

def safe_int(value: str, default: int = 0) -> int:
    """Safely convert string to int with fallback (GUI-only function)"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def get_base_dir() -> str:
    """Get base directory - works for both Python script and PyInstaller EXE"""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller EXE
        return os.path.dirname(sys.executable)
    else:
        # Running as Python script
        return os.path.dirname(os.path.abspath(__file__))


# Absolute base directory (works in EXE and script modes)
BASE_DIR = get_base_dir()


class LifeCalendarGUI:
    """Main GUI Application for Life Calendar Wallpaper Generator"""
    
    # Resolution presets
    RESOLUTION_PRESETS = {
        "1920x1080 (Full HD)": (1920, 1080),
        "2560x1440 (2K QHD)": (2560, 1440),
        "3840x2160 (4K UHD)": (3840, 2160),
        "1366x768 (HD)": (1366, 768),
        "1280x720 (720p)": (1280, 720),
        "Auto-detect": None,
        "Custom": None,
    }
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Life Calendar Wallpaper Generator")
        self.root.minsize(520, 720)
        self.root.configure(bg="#050505")
        self.root.resizable(True, True)
        
        # Use absolute config path
        self.config_file = os.path.join(BASE_DIR, "life_calendar_config.json")
        
        self.load_config()
        self.create_ui()
        
        # Keyboard shortcuts
        self.root.bind('<Return>', lambda e: threading.Thread(target=self.generate_and_set, daemon=True).start())
        self.root.bind('<Escape>', lambda e: self.root.quit())
    
    def load_config(self) -> None:
        """Load saved configuration with safety for missing keys"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    base = self._default_config()
                    base.update(loaded)
                    self.config = base
            else:
                self.config = self._default_config()
        except json.JSONDecodeError:
            self.config = self._default_config()
        except OSError:
            self.config = self._default_config()
        
        # Migrate old config versions
        if self.config.get("config_version", 1) < 2:
            self.config["config_version"] = 2
    
    def _default_config(self) -> Dict[str, Any]:
        """Return default configuration"""
        return {
            'config_version': 2,
            'mode': 'life',
            'dob': '',
            'lifespan': 90,
            'goal_start': '',
            'goal_end': '',
            'goal_title': '',
            'goal_subtitle': '',
            'resolution_width': 1920,
            'resolution_height': 1080
        }
    
    def save_config(self) -> None:
        """Save configuration to file with backup"""
        try:
            # Create backup before overwriting
            if os.path.exists(self.config_file):
                shutil.copy(self.config_file, self.config_file + ".bak")
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
        except OSError as e:
            messagebox.showerror("Error", f"Failed to save config: {e}")
    
    def create_ui(self) -> None:
        """Create the UI"""
        # Title
        title = tk.Label(
            self.root,
            text="Life Calendar Wallpaper",
            font=("Arial", 24, "bold"),
            bg="#050505",
            fg="#f2f2f2"
        )
        title.pack(pady=20)
        
        subtitle = tk.Label(
            self.root,
            text="Multi-mode calendar wallpaper generator",
            font=("Arial", 11),
            bg="#050505",
            fg="#9a9a9a"
        )
        subtitle.pack(pady=(0, 20))
        
        # Mode selector
        mode_frame = tk.Frame(self.root, bg="#050505")
        mode_frame.pack(pady=10)
        
        tk.Label(
            mode_frame, 
            text="Calendar Mode:", 
            bg="#050505", 
            fg="#9a9a9a", 
            font=("Arial", 10)
        ).pack(side="left", padx=(0, 10))
        
        self.mode_var = tk.StringVar(value=self.config.get('mode', 'life'))
        mode_dropdown = ttk.Combobox(
            mode_frame,
            textvariable=self.mode_var,
            values=['life', 'year', 'goal'],
            state='readonly',
            width=15
        )
        mode_dropdown.pack(side="left")
        mode_dropdown.bind('<<ComboboxSelected>>', self.on_mode_change)
        
        # Settings Frame
        self.settings_frame = tk.Frame(self.root, bg="#1a1a1a", bd=0)
        self.settings_frame.pack(padx=40, pady=10, fill="both", expand=True)
        
        # Create mode-specific settings
        self.create_life_settings()
        self.create_year_settings()
        self.create_goal_settings()
        
        # Resolution settings
        self.create_resolution_settings()
        
        # Show appropriate settings
        self.on_mode_change()
        
        # Buttons
        btn_frame = tk.Frame(self.root, bg="#050505")
        btn_frame.pack(pady=15)
        
        generate_btn = tk.Button(
            btn_frame,
            text="Generate & Set Wallpaper",
            font=("Arial", 12, "bold"),
            bg="#2f2f2f",
            fg="#f2f2f2",
            activebackground="#3a3a3a",
            relief="flat",
            bd=0,
            padx=25,
            pady=12,
            cursor="hand2",
            command=lambda: threading.Thread(target=self.generate_and_set, daemon=True).start()
        )
        generate_btn.pack(side="left", padx=5)
        
        preview_btn = tk.Button(
            btn_frame,
            text="Preview",
            font=("Arial", 11),
            bg="#1f1f1f",
            fg="#d6d6d6",
            activebackground="#262626",
            relief="flat",
            bd=0,
            padx=20,
            pady=12,
            cursor="hand2",
            command=lambda: threading.Thread(target=self.preview_wallpaper, daemon=True).start()
        )
        preview_btn.pack(side="left", padx=5)
        
        # Status
        self.status_label = tk.Label(
            self.root,
            text="Select mode and configure settings (Enter to generate, Esc to quit)",
            font=("Arial", 9),
            bg="#050505",
            fg="#64748b"
        )
        self.status_label.pack(pady=(0, 10))
    
    def create_life_settings(self) -> None:
        """Create Life Calendar settings"""
        self.life_frame = tk.Frame(self.settings_frame, bg="#1a1a1a")
        
        # DOB
        tk.Label(
            self.life_frame, 
            text="Date of Birth", 
            font=("Arial", 10), 
            bg="#1a1a1a", 
            fg="#9a9a9a"
        ).pack(anchor="w", padx=20, pady=(15, 5))
        
        self.dob_entry = tk.Entry(
            self.life_frame, 
            font=("Arial", 11), 
            bg="#0f0f0f", 
            fg="#f2f2f2", 
            relief="flat", 
            bd=5,
            insertbackground="#f2f2f2"
        )
        self.dob_entry.pack(fill="x", padx=20)
        self.dob_entry.insert(0, self.config.get('dob', ''))
        
        tk.Label(
            self.life_frame, 
            text="Format: YYYY-MM-DD (e.g., 1990-05-15)", 
            font=("Arial", 8), 
            bg="#1a1a1a", 
            fg="#64748b"
        ).pack(anchor="w", padx=20, pady=(2, 0))
        
        # Lifespan
        tk.Label(
            self.life_frame, 
            text="Expected Lifespan (Years)", 
            font=("Arial", 10), 
            bg="#1a1a1a", 
            fg="#9a9a9a"
        ).pack(anchor="w", padx=20, pady=(12, 5))
        
        self.lifespan_entry = tk.Entry(
            self.life_frame, 
            font=("Arial", 11), 
            bg="#0f0f0f", 
            fg="#f2f2f2", 
            relief="flat", 
            bd=5,
            insertbackground="#f2f2f2"
        )
        self.lifespan_entry.pack(fill="x", padx=20)
        self.lifespan_entry.insert(0, str(self.config.get('lifespan', 90)))
        
        tk.Label(
            self.life_frame, 
            text="Between 1-150 years", 
            font=("Arial", 8), 
            bg="#1a1a1a", 
            fg="#64748b"
        ).pack(anchor="w", padx=20, pady=(2, 0))
    
    def create_year_settings(self) -> None:
        """Create Year Calendar settings"""
        self.year_frame = tk.Frame(self.settings_frame, bg="#1a1a1a")
        
        tk.Label(
            self.year_frame,
            text="Year Progress Calendar",
            font=("Arial", 11, "bold"),
            bg="#1a1a1a",
            fg="#f2f2f2"
        ).pack(anchor="w", padx=20, pady=(15, 10))
        
        info_text = (
            "✓ Always uses current system date\n"
            "✓ Auto-updates daily at midnight\n"
            "✓ No configuration needed\n"
            "✓ Shows day progress for the current year"
        )
        tk.Label(
            self.year_frame,
            text=info_text,
            font=("Arial", 9),
            bg="#1a1a1a",
            fg="#9a9a9a",
            justify="left"
        ).pack(anchor="w", padx=20, pady=(0, 10))
        
        # Show current date info
        today = date.today()
        current_info = f"Today: {today.strftime('%B %d, %Y')} (Day {today.timetuple().tm_yday})"
        tk.Label(
            self.year_frame,
            text=current_info,
            font=("Arial", 10),
            bg="#1a1a1a",
            fg="#cfcfcf"
        ).pack(anchor="w", padx=20, pady=(5, 0))
    
    def create_goal_settings(self) -> None:
        """Create Goal Calendar settings"""
        self.goal_frame = tk.Frame(self.settings_frame, bg="#1a1a1a")
        
        # Goal Title
        tk.Label(
            self.goal_frame, 
            text="Goal Title *", 
            font=("Arial", 10), 
            bg="#1a1a1a", 
            fg="#9a9a9a"
        ).pack(anchor="w", padx=20, pady=(10, 5))
        
        self.goal_title_entry = tk.Entry(
            self.goal_frame, 
            font=("Arial", 11), 
            bg="#0f0f0f", 
            fg="#f2f2f2", 
            relief="flat", 
            bd=5,
            insertbackground="#f2f2f2"
        )
        self.goal_title_entry.pack(fill="x", padx=20)
        self.goal_title_entry.insert(0, self.config.get('goal_title', ''))
        
        # Goal Subtitle (Optional)
        tk.Label(
            self.goal_frame, 
            text="Subtitle (Optional)", 
            font=("Arial", 9), 
            bg="#1a1a1a", 
            fg="#9a9a9a"
        ).pack(anchor="w", padx=20, pady=(8, 5))
        
        self.goal_subtitle_entry = tk.Entry(
            self.goal_frame, 
            font=("Arial", 10), 
            bg="#0f0f0f", 
            fg="#d6d6d6", 
            relief="flat", 
            bd=5,
            insertbackground="#d6d6d6"
        )
        self.goal_subtitle_entry.pack(fill="x", padx=20)
        self.goal_subtitle_entry.insert(0, self.config.get('goal_subtitle', ''))
        
        # Start Date
        tk.Label(
            self.goal_frame, 
            text="Goal Start Date *", 
            font=("Arial", 10), 
            bg="#1a1a1a", 
            fg="#9a9a9a"
        ).pack(anchor="w", padx=20, pady=(15, 5))
        
        self.goal_start_entry = tk.Entry(
            self.goal_frame, 
            font=("Arial", 11), 
            bg="#0f0f0f", 
            fg="#f2f2f2", 
            relief="flat", 
            bd=5,
            insertbackground="#f2f2f2"
        )
        self.goal_start_entry.pack(fill="x", padx=20)
        self.goal_start_entry.insert(0, self.config.get('goal_start', ''))
        
        # End Date
        tk.Label(
            self.goal_frame, 
            text="Goal End Date *", 
            font=("Arial", 10), 
            bg="#1a1a1a", 
            fg="#9a9a9a"
        ).pack(anchor="w", padx=20, pady=(12, 5))
        
        self.goal_end_entry = tk.Entry(
            self.goal_frame, 
            font=("Arial", 11), 
            bg="#0f0f0f", 
            fg="#f2f2f2", 
            relief="flat", 
            bd=5,
            insertbackground="#f2f2f2"
        )
        self.goal_end_entry.pack(fill="x", padx=20)
        self.goal_end_entry.insert(0, self.config.get('goal_end', ''))
        
        tk.Label(
            self.goal_frame, 
            text="Format: YYYY-MM-DD (* = required)", 
            font=("Arial", 8), 
            bg="#1a1a1a", 
            fg="#64748b"
        ).pack(anchor="w", padx=20, pady=(2, 0))
    
    def create_resolution_settings(self) -> None:
        """Create resolution settings with presets"""
        self.res_frame = tk.Frame(self.settings_frame, bg="#1a1a1a")
        self.res_frame.pack(fill="x", padx=20, pady=(15, 10))
        
        tk.Label(
            self.res_frame, 
            text="Screen Resolution", 
            font=("Arial", 10), 
            bg="#1a1a1a", 
            fg="#9a9a9a"
        ).pack(anchor="w")
        
        # Preset dropdown - sync with loaded config
        preset_frame = tk.Frame(self.res_frame, bg="#1a1a1a")
        preset_frame.pack(anchor="w", pady=5)
        
        # Determine preset from config
        config_width = self.config.get('resolution_width', 1920)
        config_height = self.config.get('resolution_height', 1080)
        current_preset = "Custom"
        for preset_name, (preset_width, preset_height) in self.RESOLUTION_PRESETS.items():
            if preset_width == config_width and preset_height == config_height:
                current_preset = preset_name
                break
        
        self.preset_var = tk.StringVar(value=current_preset)
        preset_dropdown = ttk.Combobox(
            preset_frame,
            textvariable=self.preset_var,
            values=list(self.RESOLUTION_PRESETS.keys()),
            state='readonly',
            width=20
        )
        preset_dropdown.pack(side="left")
        preset_dropdown.bind('<<ComboboxSelected>>', self.on_preset_change)
        
        # Custom resolution inputs
        res_input = tk.Frame(self.res_frame, bg="#1a1a1a")
        res_input.pack(anchor="w", pady=5)
        
        self.width_entry = tk.Entry(
            res_input, 
            font=("Arial", 11), 
            bg="#0f0f0f", 
            fg="#f2f2f2", 
            width=8, 
            relief="flat", 
            bd=5,
            insertbackground="#f2f2f2"
        )
        self.width_entry.pack(side="left")
        self.width_entry.insert(0, str(self.config.get('resolution_width', 1920)))
        
        tk.Label(
            res_input, 
            text="×", 
            bg="#1a1a1a", 
            fg="#9a9a9a", 
            font=("Arial", 11)
        ).pack(side="left", padx=5)
        
        self.height_entry = tk.Entry(
            res_input, 
            font=("Arial", 11), 
            bg="#0f0f0f", 
            fg="#f2f2f2", 
            width=8, 
            relief="flat", 
            bd=5,
            insertbackground="#f2f2f2"
        )
        self.height_entry.pack(side="left")
        self.height_entry.insert(0, str(self.config.get('resolution_height', 1080)))
        
        tk.Label(
            self.res_frame, 
            text="Minimum: 800×600", 
            font=("Arial", 8), 
            bg="#1a1a1a", 
            fg="#64748b"
        ).pack(anchor="w")
    
    def on_preset_change(self, event=None) -> None:
        """Handle resolution preset changes"""
        preset = self.preset_var.get()
        
        if preset == "Auto-detect":
            width, height = get_screen_resolution()
        elif preset == "Custom":
            return  # Don't change custom values
        else:
            resolution = self.RESOLUTION_PRESETS.get(preset)
            if resolution:
                width, height = resolution
            else:
                return
        
        # Update entry fields
        self.width_entry.delete(0, tk.END)
        self.width_entry.insert(0, str(width))
        self.height_entry.delete(0, tk.END)
        self.height_entry.insert(0, str(height))
    
    def on_mode_change(self, event=None) -> None:
        """Handle mode changes"""
        mode = self.mode_var.get()
        
        # Hide all mode frames
        for frame in [self.life_frame, self.year_frame, self.goal_frame]:
            frame.pack_forget()
        
        # Show selected mode frame
        if mode == 'life':
            self.life_frame.pack(fill="x")
        elif mode == 'year':
            self.year_frame.pack(fill="x")
        elif mode == 'goal':
            self.goal_frame.pack(fill="x")
        
        # Resolution always shown
        self.res_frame.pack_forget()
        self.res_frame.pack(fill="x", padx=20, pady=(15, 10))
    
    def _sync_config_from_ui(self) -> bool:
        """
        Sync config from UI inputs.
        Returns True if valid, False otherwise.
        """
        mode = self.mode_var.get()
        self.config['mode'] = mode
        
        # Life mode validation
        if mode == 'life':
            dob = self.dob_entry.get().strip()
            if not dob:
                messagebox.showerror("Validation Error", "Date of Birth is required")
                return False
            
            if safe_date(dob) is None:
                messagebox.showerror("Invalid Date", "DOB must be YYYY-MM-DD format")
                return False
            
            self.config['dob'] = dob
            
            # Strict lifespan validation - no silent conversion
            lifespan_str = self.lifespan_entry.get().strip()
            if not lifespan_str or not lifespan_str.isdigit():
                messagebox.showerror("Validation Error", "Lifespan must be a number (1-150 years)")
                return False
            
            lifespan = int(lifespan_str)
            if lifespan < 1 or lifespan > 150:
                messagebox.showerror("Validation Error", "Lifespan must be between 1 and 150 years")
                return False
            
            self.config['lifespan'] = lifespan
        
        # Goal mode validation
        elif mode == 'goal':
            title = self.goal_title_entry.get().strip()
            if not title:
                messagebox.showerror("Validation Error", "Goal Title is required")
                return False
            
            start = self.goal_start_entry.get().strip()
            end = self.goal_end_entry.get().strip()
            
            if not start or not end:
                messagebox.showerror("Validation Error", "Start and End dates are required")
                return False
            
            start_date = safe_date(start)
            end_date = safe_date(end)
            
            if start_date is None:
                messagebox.showerror("Invalid Date", "Start date must be YYYY-MM-DD format")
                return False
            
            if end_date is None:
                messagebox.showerror("Invalid Date", "End date must be YYYY-MM-DD format")
                return False
            
            if end_date <= start_date:
                messagebox.showerror("Invalid Dates", "End date must be after start date")
                return False
            
            self.config['goal_start'] = start
            self.config['goal_end'] = end
            self.config['goal_title'] = title
            self.config['goal_subtitle'] = self.goal_subtitle_entry.get().strip()
        
        # Resolution validation
        width = safe_int(self.width_entry.get(), 1920)
        height = safe_int(self.height_entry.get(), 1080)
        
        if width < 800 or height < 600:
            messagebox.showerror("Resolution Error", "Minimum resolution is 800×600")
            return False
        
        self.config['resolution_width'] = width
        self.config['resolution_height'] = height
        
        return True
    
    def generate_and_set(self) -> None:
        """Generate and set wallpaper using ENGINE"""
        # Validate and sync config
        if not self._sync_config_from_ui():
            return
        
        # Save config FIRST (so auto_update.py can use it)
        self.save_config()
        
        # Use ENGINE for generation
        self.status_label.config(text="Generating wallpaper...")
        self.root.update_idletasks()
        
        try:
            engine = WallpaperEngine(self.config_file)
            success = engine.run_auto()  # Generate and set wallpaper immediately
            if success:
                messagebox.showinfo(
                    "Success",
                    f"Wallpaper set successfully!\n\n"
                    f"✓ Daily updates scheduled at midnight"
                )
                self.status_label.config(text="✓ Wallpaper active")
            else:
                messagebox.showerror(
                    "Error",
                    "Failed to generate or set wallpaper.\nCheck wallpaper.log for details."
                )
                self.status_label.config(text="Error generating wallpaper")
        
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.status_label.config(text=f"Error: {str(e)}")
    
    def preview_wallpaper(self) -> None:
        """Preview wallpaper using ENGINE"""
        # Validate and sync config
        if not self._sync_config_from_ui():
            return
        
        self.save_config()
        
        self.status_label.config(text="Generating preview...")
        self.root.update_idletasks()
        
        try:
            engine = WallpaperEngine(self.config_file)
            success, message = engine.generate_wallpaper()
            
            if success:
                from PIL import Image
                Image.open(engine.wallpaper_path).show()
                self.status_label.config(text="Preview opened")
            else:
                messagebox.showerror("Error", message)
                self.status_label.config(text=message)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.status_label.config(text=f"Error: {str(e)}")
    
    def run(self) -> None:
        """Run application"""
        self.root.mainloop()


if __name__ == "__main__":
    app = LifeCalendarGUI()
    app.run()