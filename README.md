# Life Calendar Wallpaper

![CI](https://github.com/MAHESH2094/life-calendar/actions/workflows/ci.yml/badge.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub release](https://img.shields.io/github/v/release/MAHESH2094/life-calendar)](https://github.com/MAHESH2094/life-calendar/releases)
[![codecov](https://codecov.io/gh/MAHESH2094/life-calendar/graph/badge.svg)](https://codecov.io/gh/MAHESH2094/life-calendar)
[![Docker Pulls](https://img.shields.io/docker/pulls/mahesh2094/life-calendar?style=flat)](https://hub.docker.com/r/mahesh2094/life-calendar)

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

![Life in Weeks](https://github.com/MAHESH2094/life-calendar/blob/main/Screenshot%202026-03-18%20233712.png?raw=true)

### Year Progress

![Year Progress](https://github.com/MAHESH2094/life-calendar/blob/main/year_progress.png?raw=true)

### Goal Progress

![Goal Progress](https://github.com/MAHESH2094/life-calendar/blob/main/goal_progress.png?raw=true)

## Quick start

### Windows

**Option A: Pre-built EXE (recommended for non-technical users)**
1. Download `LifeCalendar.exe` from the latest [GitHub Release](https://github.com/MAHESH2094/life-calendar/releases)
2. Double-click to run – the GUI opens automatically
3. Fill in your date of birth, lifespan, and resolution
4. Press **Enter** (or click the button) – your wallpaper changes immediately
5. A Windows Task Scheduler entry is created automatically – the wallpaper updates at midnight every night

**Option B: From source**
```bash
pip install -r requirements.txt
python life_calendar_gui.py
python life_calendar_cli.py --install-win
```

### macOS (From source)

```bash
pip install -r requirements.txt
python life_calendar_gui.py                    # Configure once (GUI opens)
python life_calendar_cli.py --install-launchd  # Auto-update nightly via LaunchAgent
```

LaunchAgent runs at 00:01 am every night and logs to `wallpaper.log`.

### Linux (From source)

```bash
pip install -r requirements.txt
python life_calendar_gui.py          # Configure once (GUI opens)
python life_calendar_cli.py --install-cron    # Auto-update nightly via cron
```

The cron job runs at 00:01 am every night. Check `cron.log` if it doesn't work.

### macOS / Linux (Docker – zero dependencies)

```bash
# One-command deployment
docker compose up -d

# Set your configuration
nano data/life_calendar_config.json

# Restart to apply changes
docker compose restart

# The container updates the wallpaper nightly automatically
```

The generated wallpaper appears in `./data/life_calendar_wallpaper.png`. You can set it as your desktop background manually or create a simple script that copies it.

## Uninstall

To completely remove Life Calendar and all scheduled tasks:

### Windows
```bash
python uninstall.py
```

### macOS / Linux
```bash
python uninstall.py
crontab -e  # Remove the life-calendar entry if needed
```

After uninstalling, your wallpaper settings and generated images are removed. The Windows Task Scheduler entry and macOS LaunchAgent are automatically cleaned up.

### How It Works

1. **Configure once** via GUI or JSON file (set date of birth, lifespan, resolution)
2. **Generate** – creates `life_calendar_wallpaper.png` 
3. **Set wallpaper** – updates your desktop background
4. **Schedule** – automatic nightly updates via Task Scheduler (Windows), cron (Linux/macOS), or Docker

---

## 🖥️ CLI Helper (all platforms)

For non-GUI users or automation:

```bash
# Generate and set wallpaper once
python life_calendar_cli.py --run-once

# Install automatic nightly updates (Linux/macOS only)
python life_calendar_cli.py --install-cron

# Install Windows Task Scheduler entry
python life_calendar_cli.py --install-win

# Show all options
python life_calendar_cli.py --help
```

The CLI automatically creates a default `life_calendar_config.json` if none exists.

---

## 🔨 For Developers

### Upgrading from v1

If you previously ran v1, make sure to reinstall dependencies:

```bash
pip install -r requirements.txt
```

### Build Standalone EXE

```bash
python build_exe.py
```

Output: `LifeCalendar_Package/LifeCalendar.exe` (GUI + headless flags)

---

## 🔧 Configuration

Edit `life_calendar_config.json` directly or use the GUI to set your dates and resolution.

### Basic configuration

```json
{
  "mode": "life",
  "dob": "1990-01-15",
  "lifespan": 90,
  "resolution_width": 1920,
  "resolution_height": 1080,
  "config_version": 4,
  "automation": {
    "startup_enabled": true,
    "wallpaper_refresh_enabled": true
  }
}
```

## 🎨 Customizing Colors

You can customize all wallpaper colors by editing the `palette` section in `life_calendar_config.json`:

```json
{
  "palette": {
    "title": "#f2f2f2",
    "stats": "#9a9a9a",
    "subtitle": "#8a8a8a",
    "legend": "#d6d6d6",
    "lived": "#cfcfcf",
    "current": "#ffffff",
    "future": "#3a3a3a",
    "current_progress": "#ffdd00"
  }
}
```

All colors use **hex format** (e.g., `#ffffff` = white, `#000000` = black). After editing, restart the application to see the changes reflected in the next wallpaper update.

---

## 🎨 Advanced configuration (custom colours and life milestones)

```json
{
  "mode": "life",
  "dob": "1990-01-15",
  "lifespan": 90,
  "resolution_width": 1920,
  "resolution_height": 1080,
  "config_version": 4,
  "automation": {
    "startup_enabled": true,
    "wallpaper_refresh_enabled": true
  },
  "palette": {
    "title": "#f2f2f2",
    "stats": "#9a9a9a",
    "subtitle": "#8a8a8a",
    "legend": "#d6d6d6",
    "lived": "#cfcfcf",
    "current": "#ffffff",
    "future": "#3a3a3a",
    "current_progress": "#ffdd00"
  },
  "opportunities": [
    {
      "name": "Warm Winters",
      "start": "2024-11-01",
      "end": "2025-02-28",
      "color": "#ff7f7f",
      "visible": true,
      "focus": false
    },
    {
      "name": "Dog-walk Season",
      "start": "2024-03-01",
      "end": "2024-05-31",
      "color": "#7fff7f",
      "visible": false,
      "focus": false
    }
  ]
}
```

**Notes:**
- Use YYYY-MM-DD format for all dates
- Colours are hex codes (e.g., `#ffffff` for white, `#000000` for black)
- Set `"visible": false` to hide an opportunity from the wallpaper
- Set `"focus": true` to highlight one opportunity with the `current_progress` color

---

## 🐛 Troubleshooting

### Wallpaper not updating?

Check `wallpaper.log` in the same folder as the config for detailed error messages.

### Windows: Task didn't auto-create?

The GUI automatically creates a Windows Task Scheduler entry when you press **Enter**. If it didn't work, you can manually recreate it:

```bash
python life_calendar_cli.py --install-win    # Requires admin privileges
```

Or via the manual Task Scheduler GUI:
1. Open Task Scheduler (press `Win+R`, type `taskschd.msc`)
2. Import `LifeCalendar_Task.xml`, or create a new task to run `LifeCalendar.exe --headless-update` daily at 00:01

### Linux/macOS: Wallpaper not changing?

Check `wallpaper.log` – different desktop environments need different commands. File an issue with your desktop environment name if it doesn't work.

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
✅ Headless updater mode (`LifeCalendar.exe --headless-update`)  
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
