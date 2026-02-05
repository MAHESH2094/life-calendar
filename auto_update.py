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

import sys
import os
from pathlib import Path


def get_base_dir() -> Path:
    """
    Get the base directory where config file is located.
    Works for both Python script and PyInstaller EXE.
    """
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller EXE - config is in same folder as EXE
        return Path(sys.executable).parent.absolute()
    else:
        # Running as Python script
        return Path(__file__).parent.absolute()


# Get correct base directory (do this ONCE at module level)
BASE_DIR = get_base_dir()


# Add base dir to path for imports (only needed for Python script, not EXE)
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(BASE_DIR))


def main() -> int:
    """
    Main entry point for auto-update.
    Returns exit code (0 = success, 1 = failure).
    """
    # Force correct working directory (critical for Task Scheduler)
    # Only do this once in main()
    try:
        os.chdir(BASE_DIR)
    except OSError as e:
        # Cannot use logger yet - print to stderr instead
        sys.stderr.write(f"ERROR: Cannot change directory to {BASE_DIR}: {e}\n")
        return 1
    
    # Import here to catch ImportError and handle gracefully
    try:
        from wallpaper_engine import WallpaperEngine, logger
    except ImportError as e:
        sys.stderr.write(f"ERROR: Failed to import wallpaper_engine: {e}\n")
        sys.stderr.write("Solution: Run 'pip install -r requirements.txt'\n")
        return 1
    
    logger.info("=" * 50)
    logger.info("Auto-update started")
    
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
                    f"Config file not found\n\n"
                    "Solution: Run LifeCalendar.exe first to create a config file."
                )
            except OSError:
                logger.error("Could not write error file")
            
            return 1
        
        # Create engine and run
        logger.info("Generating wallpaper...")
        engine = WallpaperEngine(str(config_file))
        success = engine.run_auto()
        
        if success:
            logger.info("Auto-update completed successfully")
            
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
                    except OSError:
                        pass
            
            return 0
        else:
            logger.error("Wallpaper generation or setting failed")
            
            # Write error file for visibility
            try:
                error_file = BASE_DIR / "ERROR_GENERATION_FAILED.txt"
                error_file.write_text(
                    "Life Calendar Error\n"
                    "===================\n"
                    "Wallpaper generation failed\n\n"
                    "Check wallpaper.log for details"
                )
            except OSError:
                logger.error("Could not write error file")
            
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
