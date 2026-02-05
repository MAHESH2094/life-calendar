# Life Calendar Wallpaper

A production-grade desktop wallpaper generator that visualizes life, year, or goal progress.
Built to be scheduler-safe, crash-resilient, and uninstall-clean.

## Features

- **Life-in-weeks visualization** – Your entire life as a grid
- **Year progress calendar** – Day-by-day tracking for current year
- **Goal countdown mode** – Custom date ranges for any objective
- **GUI configuration + headless updater** – Point-and-click setup, background automation
- **Windows / Linux / macOS support** – Multi-OS compatible
- **Safe for Task Scheduler / cron** – Absolute paths, no relative dependencies
- **Atomic file locking** – Race-condition safe, crash-resilient
- **Portable uninstall** – No registry writes, all files in one directory



## Screenshots

### Life in Weeks

![Life in Weeks](docs/screenshots/life_weeks.png)

### Year Progress

![Year Progress](docs/screenshots/year_progress.png)

### Goal Progress

![Goal Progress](docs/screenshots/goal_progress.png)



Year Progress
## How It Works

**GUI Mode** (`LifeCalendar.exe`)
- Configure calendar mode, dates, resolution
- Generate and immediately set wallpaper
- Save settings to config file

**Headless Mode** (`LifeCalendarUpdate.exe`)
- Runs silently via Task Scheduler (Windows) / cron (Linux/macOS)
- Regenerates wallpaper based on saved config
- Updates desktop automatically

**Engine** (`wallpaper_engine.py`)
- Pure generation logic
- Strict validation, comprehensive logging
- Portable across operating systems

## Installation

### From Source

```bash
pip install -r requirements.txt
python life_calendar_gui.py
```

### Build Standalone EXE

```bash
python build_exe.py
```

Output: `LifeCalendar_Package/LifeCalendar.exe` (GUI) and `LifeCalendarUpdate.exe` (headless)

## Development

- `wallpaper_engine.py` – Calendar generation, file locking, cross-platform wallpaper setting
- `life_calendar_gui.py` – PyQt6 configuration interface
- `auto_update.py` – Task scheduler integration
- `build_exe.py` – PyInstaller packaging

## Testing

All tests are production-level:
- Config corruption handling
- Lock race conditions
- Scheduler working directory independence
- Crash recovery (stale lock detection)
- Absolute path resolution
- Multi-platform compatibility

See `wallpaper.log` for execution details.

## License

MIT
  "lifespan": 90,
  "resolution_width": 1920,
  "resolution_height": 1080
}
```

Edit this file directly or use the GUI.

---

## 🐛 Troubleshooting

### Wallpaper not updating?

Check `wallpaper.log` in the same folder as the EXE for detailed error messages.

### Task didn't auto-create?

Run LifeCalendarUpdate.exe manually once - it will create the task on first run.

### Linux: Wallpaper not changing?

Check `wallpaper.log` - different desktop environments need different commands. File an issue with your DE name.

---

## 📝 Development

### Build EXE

```bash
# Install build dependencies
pip install pyinstaller pillow screeninfo

# Build
python build_exe.py
```

### Project Layout

```
life_calendar/
├── life_calendar_gui.py      # GUI interface
├── wallpaper_engine.py       # Core generation logic
├── auto_update.py            # Headless scheduler runner
├── build_exe.py              # Build script
├── requirements.txt          # Dependencies
└── LifeCalendar_Package/     # Distribution folder (built by build_exe.py)
    ├── LifeCalendar.exe
    ├── LifeCalendarUpdate.exe
    ├── life_calendar_config.json
    └── wallpaper.log
```

---

## 📋 What Changed (v2.0 → Production)

✅ Auto Task Scheduler registration (no INSTALL.bat needed)  
✅ Threading for non-freezing GUI  
✅ Headless updater (`LifeCalendarUpdate.exe`)  
✅ Pure logging (no console prints)  
✅ Pixel-perfect rendering (no blur)  
✅ Config safety (missing keys won't crash)  
✅ Fail-fast validation  
✅ Auto-first-wallpaper on GUI save  

---

## 📄 License

MIT - Use freely, modify, distribute.

---

## 🙏 Credits

- Inspired by Tim Urban's ["Your Life in Weeks"](https://waitbutwhy.com/2014/05/life-weeks.html)
- Built with Python, PIL, tkinter

---

**Made for people who want beautiful reminders of time, without technical distractions.**
