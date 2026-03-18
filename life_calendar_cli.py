#!/usr/bin/env python3
"""
Simple command-line helper that:

* writes a default config if none exists,
* runs the headless generator once,
* optionally installs a nightly cron job (Linux/macOS) or a Windows task.
"""

import os
import sys
import json
import subprocess
import platform
import shlex
from pathlib import Path
from wallpaper_engine import WallpaperEngine, LOG_PATH

BASE_DIR = Path(__file__).parent.absolute()
CONFIG_PATH = BASE_DIR / "life_calendar_config.json"


def _ensure_config():
    """Ensure config file exists with default values"""
    if not CONFIG_PATH.exists():
        # Use the default template from the engine
        engine = WallpaperEngine(str(CONFIG_PATH))
        default = engine.DEFAULT_CONFIG
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=2)
        print(f"✓ Created default config at {CONFIG_PATH}")
    else:
        print(f"✓ Config already present at {CONFIG_PATH}")


def _run_once():
    """Generate and set wallpaper once, then exit"""
    engine = WallpaperEngine(str(CONFIG_PATH))
    ok, msg = engine.run_auto()
    print(msg)
    if ok:
        print(f"✓ Wallpaper generated successfully.")
    sys.exit(0 if ok else 1)


def _install_cron():
    """Install a nightly cron job (Linux/macOS only)"""
    if platform.system() == "Windows":
        print("ERROR: Cron is not used on Windows – use --install-win instead.")
        sys.exit(1)
    
    wrapper = BASE_DIR / "cron_wrapper.sh"
    if not wrapper.exists():
        print(f"ERROR: {wrapper} not found. Please ensure cron_wrapper.sh is in the repo.")
        sys.exit(1)
    
    cron_line = f"1 0 * * * {shlex.quote(str(wrapper))} >> {BASE_DIR}/cron.log 2>&1"
    
    # Check if already installed
    try:
        existing = subprocess.check_output(["crontab", "-l"], stderr=subprocess.DEVNULL).decode()
    except subprocess.CalledProcessError:
        existing = ""
    
    if cron_line in existing:
        print("✓ Cron job already installed.")
        return
    
    # Add the new cron line
    new_tab = existing + ("\n" if existing else "") + cron_line + "\n"
    try:
        result = subprocess.run(
            ["crontab", "-"],
            input=new_tab.encode(),
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            print("✓ Cron job installed (runs nightly at 00:01 am).")
            print(f"   Logs will be written to: {BASE_DIR}/cron.log")
        else:
            print(f"ERROR: Failed to install cron job: {result.stderr.decode()}")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: Could not install cron job: {e}")
        sys.exit(1)


def _install_windows_task():
    """Create a Windows Task Scheduler entry"""
    if platform.system() != "Windows":
        print("ERROR: Windows task creation only works on Windows.")
        sys.exit(1)
    
    # Try to find the EXE (built by build_exe.py)
    exe_path = BASE_DIR / "LifeCalendar_Package" / "LifeCalendarUpdate.exe"
    if not exe_path.exists():
        # Fallback to Python script
        exe_path = str(BASE_DIR / "auto_update.py")
        print(f"⚠ EXE not found, using Python script: {exe_path}")
    
    # Create task via schtasks (requires admin on Windows 7+)
    cmd = [
        "schtasks", "/Create",
        "/SC", "DAILY",
        "/TN", "LifeCalendarWallpaper",
        "/TR", str(exe_path),
        "/ST", "00:01",
        "/F"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✓ Windows Task Scheduler entry created.")
            print("   The wallpaper will update daily at 00:01 am.")
        else:
            # Check for common error codes
            if "access denied" in result.stderr.lower():
                print("ERROR: Access denied. Please run this command as Administrator.")
            else:
                print(f"ERROR: Failed to create task: {result.stderr}")
            sys.exit(1)
    except subprocess.TimeoutExpired:
        print("ERROR: Task creation timed out.")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Could not create Windows task: {e}")
        sys.exit(1)


def main():
    """Main CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Life Calendar - Setup & Management Helper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python life_calendar_cli.py --run-once       # Generate wallpaper once
  python life_calendar_cli.py --install-cron   # Install nightly cron job (macOS/Linux)
  python life_calendar_cli.py --install-win    # Install Task Scheduler entry (Windows)
        """
    )
    
    parser.add_argument(
        "--install-cron",
        action="store_true",
        help="Create a nightly cron job (Linux/macOS)"
    )
    parser.add_argument(
        "--install-win",
        action="store_true",
        help="Create a Windows Task Scheduler entry"
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Generate & set wallpaper once and exit"
    )
    
    args = parser.parse_args()
    
    # Ensure config exists first
    _ensure_config()
    
    # Execute the requested action
    if args.install_cron:
        _install_cron()
    elif args.install_win:
        _install_windows_task()
    elif args.run_once:
        _run_once()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
