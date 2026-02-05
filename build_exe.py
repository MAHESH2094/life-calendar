"""
Build Script - Creates standalone EXE files for distribution
Run: python build_exe.py

Requirements:
  pip install pyinstaller pillow screeninfo

Output:
  LifeCalendar_Package/
  ├── LifeCalendar.exe           (GUI - run anytime to configure)
  ├── LifeCalendarUpdate.exe     (Headless - runs silently via Task Scheduler)
  ├── life_calendar_config.json  (default config)
  └── README.txt                 (user instructions)
"""

import subprocess
import shutil
import os
import sys
from pathlib import Path

# Project version - used for naming
PROJECT_VERSION = "2.0.0"

# Paths
BASE_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = BASE_DIR / "LifeCalendar_Package"
DIST_DIR = BASE_DIR / "dist"
BUILD_DIR = BASE_DIR / "build"


def cleanup():
    """Clean build artifacts BEFORE building"""
    print("[CLEAN] Removing old build artifacts...")
    
    for dir_path in [BUILD_DIR, DIST_DIR]:
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"        Removed {dir_path.name}/")
    
    for spec_file in BASE_DIR.glob("*.spec"):
        spec_file.unlink()
        print(f"        Removed {spec_file.name}")


def run_command(cmd: list, description: str) -> bool:
    """Run a command and return success status"""
    print(f"\n[BUILD] {description}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"[OK]    {description} - SUCCESS")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[FAIL]  {description} - FAILED")
        print(f"        Error: {e}")
        return False
    except FileNotFoundError:
        print(f"[FAIL]  {description} - FAILED")
        print("        PyInstaller not found. Install with: pip install pyinstaller")
        return False


def build_gui():
    """Build the GUI application"""
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "LifeCalendar",
        "--clean",
        "--noconfirm",
        "--hidden-import=screeninfo",
        "--hidden-import=PIL",
        str(BASE_DIR / "life_calendar_gui.py")
    ]
    return run_command(cmd, "Building GUI (LifeCalendar.exe)")


def build_updater():
    """Build the headless updater - SILENT, NO CONSOLE"""
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--noconsole",  # NO CONSOLE - runs silently
        "--name", "LifeCalendarUpdate",
        "--clean",
        "--noconfirm",
        "--hidden-import=screeninfo",
        "--hidden-import=PIL",
        str(BASE_DIR / "auto_update.py")
    ]
    return run_command(cmd, "Building Updater (LifeCalendarUpdate.exe)")


def verify_exes_exist():
    """Hard fail if EXEs are missing"""
    gui_exe = DIST_DIR / "LifeCalendar.exe"
    update_exe = DIST_DIR / "LifeCalendarUpdate.exe"
    
    if not gui_exe.exists():
        raise RuntimeError(f"FATAL: GUI EXE not found: {gui_exe}")
    
    if not update_exe.exists():
        raise RuntimeError(f"FATAL: Updater EXE not found: {update_exe}")


def create_package():
    """Create the distribution package folder"""
    print(f"\n[PACKAGE] Creating distribution package...")
    
    # Verify EXEs exist before packaging
    try:
        verify_exes_exist()
    except RuntimeError as e:
        print(f"[FAIL]   {e}")
        raise
    
    # Clean and create output directory
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)
    
    # Copy EXE files
    gui_exe = DIST_DIR / "LifeCalendar.exe"
    update_exe = DIST_DIR / "LifeCalendarUpdate.exe"
    
    shutil.copy(gui_exe, OUTPUT_DIR)
    print(f"[OK]     Copied LifeCalendar.exe")
    
    shutil.copy(update_exe, OUTPUT_DIR)
    print(f"[OK]     Copied LifeCalendarUpdate.exe")
    
    # Copy config file
    config_file = BASE_DIR / "life_calendar_config.json"
    if config_file.exists():
        shutil.copy(config_file, OUTPUT_DIR)
        print(f"[OK]     Copied life_calendar_config.json")
    
    # Copy README
    readme_file = BASE_DIR / "README.txt"
    if readme_file.exists():
        shutil.copy(readme_file, OUTPUT_DIR)
        print(f"[OK]     Copied README.txt")
    
    print(f"[OK]     Package created: {OUTPUT_DIR}")


def cleanup_after():
    """Clean up build artifacts AFTER packaging"""
    print(f"\n[CLEAN]  Cleaning up build artifacts...")
    
    for dir_path in [BUILD_DIR, DIST_DIR]:
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"         Removed {dir_path.name}/")
    
    for spec_file in BASE_DIR.glob("*.spec"):
        spec_file.unlink()
        print(f"         Removed {spec_file.name}")


def main():
    print(f"""
========================================================
            LIFE CALENDAR - BUILD v{PROJECT_VERSION}
========================================================

This script creates standalone EXE files for distribution
""")
    
    # Check PyInstaller
    try:
        import PyInstaller
        print(f"[OK]     PyInstaller v{PyInstaller.__version__} found")
    except ImportError:
        print("[FAIL]   PyInstaller not installed!")
        print("         Run: pip install pyinstaller")
        sys.exit(1)
    
    try:
        # Clean BEFORE building
        cleanup()
        
        # Build both EXEs
        gui_success = build_gui()
        if not gui_success:
            raise RuntimeError("GUI build failed")
        
        update_success = build_updater()
        if not update_success:
            raise RuntimeError("Updater build failed")
        
        # Package EXEs
        create_package()
        
        # Clean AFTER packaging
        cleanup_after()
        
        print(f"""
========================================================
                  BUILD COMPLETE!
========================================================

Package: {OUTPUT_DIR}

Files:
  - LifeCalendar.exe         (GUI, {PROJECT_VERSION})
  - LifeCalendarUpdate.exe   (Headless updater, silent)
  - life_calendar_config.json (default configuration)
  - README.txt               (user guide)

Ready to distribute!

========================================================
""")
        
    except Exception as e:
        print(f"\n[FAIL]   Build failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
