"""
Life Calendar Uninstall Script

Completely removes the Life Calendar application and all associated files.

What it removes:
  • Windows Task Scheduler entry (if installed)
  • macOS LaunchAgent plist (if installed)
  • Generated wallpaper files
  • Log files and temporary files
  • Lock files and state

Usage:
  python uninstall.py

Or double-click uninstall_LifeCalendar.bat (Windows)

After running this script, all Life Calendar scheduled tasks are removed.
Manual cron removal on Linux/macOS: run `crontab -e` and delete the Life Calendar entry.
"""

import sys
import subprocess
import platform
from pathlib import Path


def get_base_dir() -> Path:
    """Get base directory - works for both Python script and PyInstaller EXE"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent.absolute()
    else:
        return Path(__file__).parent.absolute()


BASE_DIR = get_base_dir()


def remove_scheduled_task() -> bool:
    """Remove Windows scheduled task"""
    if platform.system() != "Windows":
        print("  [SKIP] Not on Windows")
        return True

    task_name = "LifeCalendarWallpaper"

    try:
        # Check if task exists
        check = subprocess.run(
            ["schtasks", "/query", "/tn", task_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        if check.returncode != 0:
            print(f"  [OK] Task '{task_name}' does not exist")
            return True

        # Delete task
        result = subprocess.run(
            ["schtasks", "/delete", "/tn", task_name, "/f"],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print(f"  [OK] Removed scheduled task '{task_name}'")
            return True
        else:
            print(f"  [FAIL] Could not remove task: {result.stderr}")
            return False

    except Exception as e:
        print(f"  [ERROR] {e}")
        return False


def remove_file(filepath: Path, description: str) -> bool:
    """Remove a file if it exists"""
    try:
        if filepath.exists():
            filepath.unlink()
            print(f"  [OK] Removed {description}: {filepath.name}")
            return True
        else:
            print(f"  [SKIP] {description} does not exist")
            return True
    except Exception as e:
        print(f"  [FAIL] Could not remove {description}: {e}")
        return False


def remove_log_files() -> bool:
    """Remove log files and backups"""
    success = True
    for log_file in BASE_DIR.glob("wallpaper.log*"):
        success = remove_file(log_file, "log file") and success
    return success


def main():
    print("=" * 50)
    print("LIFE CALENDAR UNINSTALLER")
    print("=" * 50)
    print(f"\nBase directory: {BASE_DIR}\n")

    all_success = True

    # 1. Remove scheduled task (Windows)
    print("[1/6] Checking scheduled task...")
    all_success = remove_scheduled_task() and all_success

    # 2. Remove timestamp file
    print("\n[2/5] Removing timestamp file...")
    timestamp_file = BASE_DIR / ".last_update_date"
    all_success = remove_file(timestamp_file, "timestamp file") and all_success

    # 3. Remove lock file
    print("\n[3/5] Removing lock file...")
    lock_file = BASE_DIR / ".life_calendar.lock"
    all_success = remove_file(lock_file, "lock file") and all_success

    # 4. Remove wallpaper file
    print("\n[4/5] Removing wallpaper...")
    wallpaper_file = BASE_DIR / "life_calendar_wallpaper.png"
    all_success = remove_file(wallpaper_file, "wallpaper") and all_success

    # 5. Remove logs
    print("\n[5/5] Removing log files...")
    all_success = remove_log_files() and all_success

    # 6. Remove error marker files
    print("\n[6/6] Removing error markers...")
    for err_file in ["ERROR_CONFIG_NOT_FOUND.txt", "ERROR_GENERATION_FAILED.txt", "ERROR_IMPORT_FAILED.txt"]:
        remove_file(BASE_DIR / err_file, "error file")

    print("\n" + "=" * 50)
    if all_success:
        print("UNINSTALL COMPLETE")
        print("\nNote: Config file (life_calendar_config.json) was NOT removed.")
        print("      Delete manually if you want to remove your settings.")
    else:
        print("UNINSTALL COMPLETED WITH ERRORS")
        print("Some items could not be removed. Check messages above.")
    print("=" * 50)

    # Keep window open on Windows
    if platform.system() == "Windows":
        input("\nPress Enter to close...")

    return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(main())
