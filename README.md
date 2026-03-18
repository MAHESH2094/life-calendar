# Life Calendar Wallpaper

A production-grade desktop wallpaper generator that visualizes life, year, or goal progress.
Built to be scheduler-safe, crash-resilient, and uninstall-clean.

## Features

* **Life-in-weeks visualization** – Your entire life as a grid of weeks.  
* **Year-progress calendar** – Day-by-day tracking for the current year.  
* **Goal-countdown mode** – Custom date ranges for any objective.  
* **Simple Tkinter GUI** – No extra GUI libraries required; runs on any recent Python.  
* **Headless updater** – Runs silently via Task Scheduler (Windows) or `cron` (Linux/macOS).  
* **Cross-platform** – Works on Windows, macOS, and Linux (multiple desktop environments).  
* **Atomic file locking & safe paths** – Crash-resilient, scheduler-friendly.

## Quick start

1. **From source** – Install the Python dependencies and launch the GUI:  
   ```bash
   pip install -r requirements.txt
   python life_calendar_gui.py   # Tkinter window opens
   ```  
2. Configure your dates, choose a mode, press **Enter** (or click the button).  
3. The wallpaper is set immediately and a daily task is created for automatic updates.  

> **Note:** The original README mentioned an `INSTALL.bat` and "PyQt6".  
> Those artefacts are no longer part of the project – the GUI uses **Tkinter**, which is bundled with Python, and there is no installer script required.

## Keyboard shortcuts

* **Enter** – Generate and set wallpaper.  
* **Esc**   – Close the application.

## Development

* `build_exe.py` – PyInstaller wrapper that produces `LifeCalendar.exe` (GUI) and `LifeCalendarUpdate.exe` (headless).  
* `auto_update.py` – The script that the scheduler runs; it does **only** the update work.  
* `life_calendar_gui.py` – Pure Tkinter UI; all heavy lifting lives in `wallpaper_engine.py`.  
* `wallpaper_engine.py` – Core generation, validation, rendering, and OS-specific wallpaper setting.

## Installation

### From Source

```bash
pip install -r requirements.txt
python life_calendar_gui.py
```

### Upgrading from v1

If you previously ran v1, make sure to reinstall dependencies:

```bash
pip install -r requirements.txt
```

### Build Standalone EXE

```bash
python build_exe.py
```

Output: `LifeCalendar_Package/LifeCalendar.exe` (GUI) and `LifeCalendarUpdate.exe` (headless)

---

## 🔧 Configuration

Edit `life_calendar_config.json` directly or use the GUI:

```json
{
  "mode": "life",
  "dob": "1990-01-15",
  "lifespan": 90,
  "resolution_width": 1920,
  "resolution_height": 1080
}
```

---

## 🐛 Troubleshooting

### Wallpaper not updating?

Check `wallpaper.log` in the same folder as the EXE for detailed error messages.

### Task didn't auto-create?

Import `LifeCalendar_Task.xml` into Task Scheduler, or set up manually via `taskschd.msc`.

### Linux: Wallpaper not changing?

Check `wallpaper.log` - different desktop environments need different commands. File an issue with your DE name.

---

## 📝 Development

### Project Layout

```
life_calendar/
├── life_calendar_gui.py      # GUI interface (tkinter)
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

### Build EXE

```bash
pip install pyinstaller pillow screeninfo
python build_exe.py
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
