#!/usr/bin/env python3
"""Simple CLI helper for one-off runs and scheduler setup."""

import json
import platform
import shlex
import subprocess
import sys
from pathlib import Path

from daily_companion import merge_config
from wallpaper_engine import WallpaperEngine, force_release_lock

BASE_DIR = Path(__file__).parent.absolute()
CONFIG_PATH = BASE_DIR / "life_calendar_config.json"


def _ensure_config() -> None:
    """Ensure a config file exists."""
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(merge_config(), indent=2), encoding="utf-8")
        print(f"Created default config at {CONFIG_PATH}")
    else:
        print(f"Config already present at {CONFIG_PATH}")


def _run_once() -> None:
    """Generate and set the wallpaper immediately."""
    engine = WallpaperEngine(str(CONFIG_PATH))
    ok = engine.run_auto()
    if ok:
        print("Wallpaper generated successfully.")
    sys.exit(0 if ok else 1)


def _release_lock() -> None:
    """Force-release the lock file for recovery scenarios."""
    released = force_release_lock("manual CLI release-lock")
    if released:
        print("Lock file released.")
    else:
        print("No lock file found.")
    sys.exit(0)


def _install_cron(cron_time: str = "1 0 * * *") -> None:
    """Install a nightly cron job on Linux or macOS."""
    if platform.system() == "Windows":
        print("ERROR: Cron is not used on Windows - use --install-win instead.")
        sys.exit(1)

    wrapper = BASE_DIR / "cron_wrapper.sh"
    if not wrapper.exists():
        print(f"ERROR: {wrapper} not found. Please ensure cron_wrapper.sh is in the repo.")
        sys.exit(1)

    log_path = shlex.quote(str(BASE_DIR / "cron.log"))
    cron_line = f"{cron_time} {shlex.quote(str(wrapper))} >> {log_path} 2>&1"
    try:
        existing = subprocess.check_output(["crontab", "-l"], stderr=subprocess.DEVNULL).decode()
    except FileNotFoundError:
        print("ERROR: crontab command not found – install cron on this system.")
        sys.exit(1)
    except subprocess.CalledProcessError:
        existing = ""

    if cron_line in existing:
        print("Cron job already installed.")
        return

    new_tab = existing + ("\n" if existing else "") + cron_line + "\n"
    try:
        result = subprocess.run(
            ["crontab", "-"],
            input=new_tab.encode(),
            capture_output=True,
            timeout=5,
        )
        if result.returncode == 0:
            print(f"Cron job installed with schedule: {cron_time}")
            print(f"Logs will be written to: {BASE_DIR}/cron.log")
        else:
            print(f"ERROR: Failed to install cron job: {result.stderr.decode()}")
            sys.exit(1)
    except Exception as exc:
        print(f"ERROR: Could not install cron job: {exc}")
        sys.exit(1)


def _install_windows_task() -> None:
    """Create a Windows Task Scheduler entry using windows_automation module."""
    if platform.system() != "Windows":
        print("ERROR: Windows task creation only works on Windows.")
        sys.exit(1)

    try:
        from windows_automation import sync_windows_tasks
        import json

        config_file = BASE_DIR / "life_calendar_config.json"
        with open(config_file, 'r') as f:
            config = json.load(f)

        # Enable both automation options
        config["automation"] = {
            "startup_enabled": True,
            "wallpaper_refresh_enabled": True,
        }

        with open(config_file, "w", encoding="utf-8") as file_handle:
            json.dump(config, file_handle, indent=2)

        success, errors = sync_windows_tasks(config, BASE_DIR)
        if success:
            print("Windows Task Scheduler entries created successfully!")
            print("  - LifeCalendarWallpaper: Updates daily at 00:01 and on unlock")
            print("  - LifeCalendarStartupPrompt: Runs at login")
        else:
            print("ERROR: Failed to create Windows tasks:")
            for error in errors:
                print(f"  - {error}")
            sys.exit(1)

    except FileNotFoundError:
        print(f"ERROR: Config file not found: {config_file}")
        sys.exit(1)
    except Exception as exc:
        print(f"ERROR: Could not create Windows tasks: {exc}")
        sys.exit(1)


def _install_launchd() -> None:
    """Create a macOS launchd plist for scheduled updates."""
    if platform.system() != "Darwin":
        print("ERROR: launchd creation only works on macOS.")
        sys.exit(1)

    import plistlib

    plist_path = Path.home() / "Library" / "LaunchAgents" / "com.lifecalendar.wallpaper.plist"
    plist_path.parent.mkdir(parents=True, exist_ok=True)

    plist_dict = {
        "Label": "com.lifecalendar.wallpaper",
        "ProgramArguments": [str(BASE_DIR / "cron_wrapper.sh")],
        "StartCalendarInterval": {
            "Hour": 0,
            "Minute": 1,
        },
        "StandardOutPath": str(BASE_DIR / "launchd.log"),
        "StandardErrorPath": str(BASE_DIR / "launchd.log"),
        "RunAtLoad": False,
    }

    try:
        plist_path.write_bytes(plistlib.dumps(plist_dict))
        result = subprocess.run(
            ["launchctl", "load", str(plist_path)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 or "already loaded" in result.stderr:
            print("macOS LaunchAgent created and loaded.")
            print(f"Plist location: {plist_path}")
            print(f"Logs will be written to: {BASE_DIR}/launchd.log")
        else:
            print(f"WARNING: LaunchAgent created but failed to load: {result.stderr}")
            print(f"You can manually load with: launchctl load {plist_path}")
    except Exception as exc:
        print(f"ERROR: Could not create launchd plist: {exc}")
        sys.exit(1)


def main() -> None:
    """CLI entrypoint."""
    import argparse

    parser = argparse.ArgumentParser(description="Life Calendar - Setup & Management Helper")
    parser.add_argument("--install-cron", action="store_true", help="Create a nightly cron job")
    parser.add_argument(
        "--cron-time",
        type=str,
        default="1 0 * * *",
        help="Cron schedule for --install-cron (default: '1 0 * * *')",
    )
    parser.add_argument("--install-launchd", action="store_true", help="Create a macOS LaunchAgent")
    parser.add_argument("--install-win", action="store_true", help="Create a Windows Task Scheduler entry")
    parser.add_argument("--run-once", action="store_true", help="Generate and set wallpaper once")
    parser.add_argument("--release-lock", action="store_true", help="Force-remove stale lock file")
    args = parser.parse_args()

    _ensure_config()

    if args.install_cron:
        _install_cron(args.cron_time)
    elif args.install_launchd:
        _install_launchd()
    elif args.install_win:
        _install_windows_task()
    elif args.run_once:
        _run_once()
    elif args.release_lock:
        _release_lock()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
