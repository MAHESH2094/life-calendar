"""
Auto Update Script - Headless Wallpaper Update
NO GUI - Scheduler friendly (Windows Task Scheduler / Linux cron)

Usage:
  Windows Task Scheduler: Runs daily at scheduled time
  Linux cron: 0 0 * * * cd /path/to/life_calendar && python3 auto_update.py

Exit Codes:
  0 = Success
  1 = Failure

NOTE: Scheduler registration is handled by GUI, not this updater.
      This script has SINGLE RESPONSIBILITY: update the wallpaper.
"""

import re
import sys
import os
from pathlib import Path
from typing import Optional


def get_base_dir() -> Path:
    """
    Get the base directory where config file is located.
    Works for both Python script and PyInstaller EXE.
    """
    env_dir = os.getenv("LIFECALENDAR_DATA_DIR", "").strip()
    if env_dir:
        data_dir = Path(env_dir).expanduser()
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir.absolute()

    if getattr(sys, 'frozen', False):
        # Running as PyInstaller EXE - config is in same folder as EXE
        return Path(sys.executable).parent.absolute()
    else:
        # Running as Python script
        return Path(__file__).parent.absolute()


# Get correct base directory (do this ONCE at module level)
BASE_DIR = get_base_dir()


def needs_update() -> bool:
    """
    Check if wallpaper was already updated today.
    Uses timestamp file to prevent duplicate updates from multiple triggers.
    Returns True if update needed, False if already done today.

    NOTE: This is READ-ONLY. Use mark_updated() after confirming success.
    """
    from datetime import date

    timestamp_file = BASE_DIR / ".last_update_date"
    today_str = str(date.today())

    try:
        if timestamp_file.exists():
            with open(timestamp_file, 'r') as f:
                last_update = f.read().strip()

            # C3: Validate timestamp format (YYYY-MM-DD) before using it
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', last_update):
                # Corrupted timestamp - treat as "needs update"
                return True

            # If last_update equals or exceeds today (handles clock jumps backward), skip
            if last_update >= today_str:
                # Already updated today, or clock jump detected - skip
                return False

        return True

    except OSError:
        # If we can't read/write timestamp, update anyway
        return True


def _wallpaper_recently_modified() -> bool:
    """
    Rate-limit guard: returns True if the wallpaper PNG was modified
    less than 5 minutes ago.  Prevents infinite-loop edge cases when
    the system clock jumps or the container restarts rapidly.
    """
    import time

    wallpaper = BASE_DIR / "life_calendar_wallpaper.png"
    try:
        if wallpaper.exists():
            age_seconds = time.time() - wallpaper.stat().st_mtime
            if age_seconds < 300:  # 5 minutes
                return True
    except OSError:
        pass
    return False


def mark_updated() -> None:
    """
    Write today's date to timestamp file.
    Call ONLY after confirming wallpaper update succeeded.
    """
    from datetime import date

    timestamp_file = BASE_DIR / ".last_update_date"
    try:
        with open(timestamp_file, 'w') as f:
            f.write(str(date.today()))
    except OSError:
        pass  # Non-critical - worst case we update again


def main(argv: Optional[list[str]] = None) -> int:
    """
    Main entry point for auto-update.
        Returns exit code (0 = success, 1 = failure).

    Args:
        argv: Optional list of command-line arguments (for testing).
              If None, uses sys.argv[1:].

    Usage:
      python auto_update.py              # Normal: generate and set wallpaper
      python auto_update.py --dry-run    # D6: Test without making changes
    """
    # D6: Parse command-line arguments
    import argparse
    parser = argparse.ArgumentParser(
        description="Auto-update wallpaper. Use --dry-run to test without changes."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test wallpaper generation without actually setting it"
    )
    args = parser.parse_args(argv)

    # Import here to catch ImportError and handle gracefully
    try:
        from wallpaper_engine import WallpaperEngine, logger, force_release_lock
    except ImportError as e:
        sys.stderr.write(f"ERROR: Failed to import wallpaper_engine: {e}\n")
        sys.stderr.write("Solution: Run 'pip install -r requirements.txt'\n")
        return 1

    logger.info("=" * 50)
    if args.dry_run:
        logger.info("Auto-update started (DRY-RUN mode)")
    else:
        logger.info("Auto-update started")

    # Unified stale lock cleanup policy is implemented in wallpaper_engine.
    # We do an optional pre-clean for obviously broken lock files only.
    lock_file = BASE_DIR / ".life_calendar.lock"
    if lock_file.exists():
        try:
            raw = lock_file.read_text(encoding="utf-8").strip()
            if not raw:
                force_release_lock("empty lock file")
        except OSError:
            # Best effort only; acquire_lock will handle hard failures.
            pass

    # Check if already updated today (prevents duplicate updates from multiple triggers)
    if not needs_update():
        logger.info("Wallpaper already updated today - skipping")
        return 0

    # Rate-limit: skip if wallpaper was modified very recently (< 5 min)
    if _wallpaper_recently_modified():
        logger.info("Wallpaper was modified less than 5 minutes ago - rate limited")
        return 0

    # NOTE: Scheduler registration is handled by GUI, not updater
    # This keeps the updater focused on a single responsibility: updating wallpaper

    try:
        # Check if config exists
        config_file = BASE_DIR / "life_calendar_config.json"
        if not config_file.exists():
            logger.error(f"Config file not found: {config_file}")

            # Create error file for user visibility
            error_file = BASE_DIR / "ERROR_CONFIG_NOT_FOUND.txt"
            try:
                error_file.write_text(
                    "Life Calendar Error\n"
                    "===================\n"
                    "Config file not found\n\n"
                    "Solution: Run LifeCalendar.exe first to create a config file."
                )
            except OSError as e:
                import errno
                if e.errno == errno.EACCES:
                    logger.error(f"Permission denied writing error file: {e}")
                elif e.errno == errno.ENOSPC:
                    logger.error(f"No space left on device: {e}")
                else:
                    logger.error(f"Could not write error file: {e}")

            return 1

        # Create engine and run
        logger.info("Generating wallpaper...")
        engine = WallpaperEngine(str(config_file))

        if args.dry_run:
            # D6: Test mode - generate but don't set or mark as updated
            try:
                from wallpaper_engine import acquire_lock, release_lock
                acquire_lock()
                try:
                    logger.info("[DRY-RUN] Testing wallpaper generation only...")
                    success, message = engine.generate_wallpaper()
                    if success:
                        logger.info(f"[DRY-RUN] Wallpaper generation successful: {message}")
                        logger.info("[DRY-RUN] (Would apply wallpaper and mark as updated in normal mode)")
                        return 0
                    else:
                        logger.error(f"[DRY-RUN] Wallpaper generation failed: {message}")
                        return 1
                finally:
                    release_lock()
            except Exception as e:
                logger.exception(f"[DRY-RUN] Test failed: {e}")
                return 1
        else:
            # Normal mode - generate and set
            success = engine.run_auto()

            if success:
                logger.info("Auto-update completed successfully")

                # Mark as updated ONLY after confirmed success
                mark_updated()

                # Clean up any old error files
                for error_file_name in [
                    "ERROR_CONFIG_NOT_FOUND.txt",
                    "ERROR_IMPORT_FAILED.txt",
                    "ERROR_GENERATION_FAILED.txt"
                ]:
                    error_file = BASE_DIR / error_file_name
                    if error_file.exists():
                        try:
                            error_file.unlink()
                        except OSError as e:
                            import errno
                            if e.errno == errno.EACCES:
                                logger.debug(f"Permission denied removing {error_file_name}")
                            elif e.errno == errno.ENOENT:
                                pass  # File already removed
                            else:
                                logger.debug(f"Could not remove {error_file_name}: {e}")

                return 0
            else:
                logger.error("Wallpaper generation or setting failed")

                # Write error file for visibility
                error_file = BASE_DIR / "ERROR_GENERATION_FAILED.txt"
                try:
                    error_file.write_text(
                        "Life Calendar Error\n"
                        "===================\n"
                        "Wallpaper generation failed\n\n"
                        "Check wallpaper.log for details"
                    )
                except OSError as e:
                    import errno
                    if e.errno == errno.EACCES:
                        logger.error(f"Permission denied writing error file: {e}")
                    elif e.errno == errno.ENOSPC:
                        logger.error(f"No space left on device: {e}")
                    else:
                        logger.error(f"Could not write error file: {e}")

                return 1

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return 1

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
