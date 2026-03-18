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

![Life in Weeks](https://github.com/MAHESH2094/life-calendar/blob/main/life_weeks.png?raw=true)

### Year Progress

![Year Progress](https://github.com/MAHESH2094/life-calendar/blob/main/year_progress.png?raw=true)

### Goal Progress

![Goal Progress](https://github.com/MAHESH2094/life-calendar/blob/main/goal_progress.png?raw=true)

## Quick start

### How It Works
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
