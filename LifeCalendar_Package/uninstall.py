"""Life Calendar cleanup helper."""

import platform
import sys
from pathlib import Path

from windows_automation import (
    STARTUP_TASK_NAME,
    WALLPAPER_TASK_NAME,
    remove_windows_task,
)


def get_base_dir() -> Path:
    """Get the base directory in both script and packaged modes."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.absolute()
    return Path(__file__).parent.absolute()


BASE_DIR = get_base_dir()


def remove_file(filepath: Path, description: str) -> bool:
    """Remove a file if it exists."""
    try:
        if filepath.exists():
            filepath.unlink()
            print(f"  [OK] Removed {description}: {filepath.name}")
        else:
            print(f"  [SKIP] {description} does not exist")
        return True
    except Exception as exc:
        print(f"  [FAIL] Could not remove {description}: {exc}")
        return False


def remove_windows_tasks() -> bool:
    """Remove both Windows scheduled tasks."""
    if platform.system() != "Windows":
        print("  [SKIP] Not on Windows")
        return True

    success = True
    for task_name in (WALLPAPER_TASK_NAME, STARTUP_TASK_NAME):
        if remove_windows_task(task_name):
            print(f"  [OK] Removed scheduled task '{task_name}' (or it did not exist)")
        else:
            print(f"  [FAIL] Could not remove scheduled task '{task_name}'")
            success = False
    return success


def remove_log_files() -> bool:
    """Remove log files and their backups."""
    success = True
    for log_file in BASE_DIR.glob("wallpaper.log*"):
        success = remove_file(log_file, "log file") and success
    return success


def main() -> int:
    print("=" * 50)
    print("LIFE CALENDAR UNINSTALLER")
    print("=" * 50)
    print(f"\nBase directory: {BASE_DIR}\n")

    all_success = True

    print("[1/7] Removing scheduled tasks...")
    all_success = remove_windows_tasks() and all_success

    print("\n[2/7] Removing timestamp file...")
    all_success = remove_file(BASE_DIR / ".last_update_date", "timestamp file") and all_success

    print("\n[3/7] Removing lock file...")
    all_success = remove_file(BASE_DIR / ".life_calendar.lock", "lock file") and all_success

    print("\n[4/7] Removing daily history...")
    all_success = remove_file(BASE_DIR / "daily_checkins.json", "daily history") and all_success

    print("\n[5/7] Removing wallpaper...")
    all_success = remove_file(BASE_DIR / "life_calendar_wallpaper.png", "wallpaper") and all_success

    print("\n[6/7] Removing log files...")
    all_success = remove_log_files() and all_success

    print("\n[7/7] Removing error markers...")
    for err_file in ("ERROR_CONFIG_NOT_FOUND.txt", "ERROR_GENERATION_FAILED.txt", "ERROR_IMPORT_FAILED.txt"):
        remove_file(BASE_DIR / err_file, "error file")

    print("\n" + "=" * 50)
    if all_success:
        print("UNINSTALL COMPLETE")
        print("\nNote: Config file (life_calendar_config.json) was NOT removed.")
        print("      Delete it manually if you also want to remove your settings.")
    else:
        print("UNINSTALL COMPLETED WITH ERRORS")
        print("Some items could not be removed. Check messages above.")
    print("=" * 50)

    if platform.system() == "Windows":
        input("\nPress Enter to close...")

    return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(main())
