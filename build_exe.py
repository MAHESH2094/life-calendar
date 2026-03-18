"""Build the single-file Windows package for Life Calendar."""

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_VERSION = "3.0.0"
BASE_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = BASE_DIR / "LifeCalendar_Package"
DIST_DIR = BASE_DIR / "dist"
BUILD_DIR = BASE_DIR / "build"


def cleanup() -> None:
    """Remove old build artifacts."""
    print("[CLEAN] Removing old build artifacts...")
    for dir_path in (BUILD_DIR, DIST_DIR):
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"        Removed {dir_path.name}/")

    for spec_file in BASE_DIR.glob("*.spec"):
        spec_file.unlink()
        print(f"        Removed {spec_file.name}")


def run_command(cmd: list[str], description: str) -> bool:
    """Run a subprocess and report success."""
    print(f"\n[BUILD] {description}")
    try:
        subprocess.run(cmd, check=True, capture_output=False)
        print(f"[OK]    {description} - SUCCESS")
        return True
    except subprocess.CalledProcessError as exc:
        print(f"[FAIL]  {description} - FAILED")
        print(f"        Error: {exc}")
        return False
    except FileNotFoundError:
        print(f"[FAIL]  {description} - FAILED")
        print("        PyInstaller not found. Install with: pip install pyinstaller")
        return False


def build_app() -> bool:
    """Build the GUI application and bundled command modes."""
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--name",
        "LifeCalendar",
        "--clean",
        "--noconfirm",
        "--hidden-import=screeninfo",
        "--hidden-import=PIL",
        "--hidden-import=auto_update",
        str(BASE_DIR / "life_calendar_gui.py"),
    ]
    return run_command(cmd, "Building LifeCalendar.exe")


def create_package() -> None:
    """Collect the packaged output."""
    print("\n[PACKAGE] Creating distribution package...")

    exe_path = DIST_DIR / "LifeCalendar.exe"
    if not exe_path.exists():
        raise RuntimeError(f"FATAL: GUI EXE not found: {exe_path}")

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    shutil.copy(exe_path, OUTPUT_DIR)
    print("[OK]     Copied LifeCalendar.exe")

    for filename in ("life_calendar_config.json", "README.txt", "uninstall.py", "windows_automation.py"):
        src = BASE_DIR / filename
        if src.exists():
            shutil.copy(src, OUTPUT_DIR)
            print(f"[OK]     Copied {filename}")

    print(f"[OK]     Package created: {OUTPUT_DIR}")


def cleanup_after() -> None:
    """Remove PyInstaller scratch artifacts after packaging."""
    print("\n[CLEAN]  Cleaning up build artifacts...")
    for dir_path in (BUILD_DIR, DIST_DIR):
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"         Removed {dir_path.name}/")

    for spec_file in BASE_DIR.glob("*.spec"):
        spec_file.unlink()
        print(f"         Removed {spec_file.name}")


def main() -> None:
    print(
        f"""
========================================================
            LIFE CALENDAR - BUILD v{PROJECT_VERSION}
========================================================

This script creates the single-file desktop package.
"""
    )

    try:
        import PyInstaller

        print(f"[OK]     PyInstaller v{PyInstaller.__version__} found")
    except ImportError:
        print("[FAIL]   PyInstaller not installed!")
        print("         Run: pip install pyinstaller")
        sys.exit(1)

    try:
        cleanup()

        if not build_app():
            raise RuntimeError("GUI build failed")

        create_package()
        cleanup_after()

        print(
            f"""
========================================================
                  BUILD COMPLETE!
========================================================

Package: {OUTPUT_DIR}

Files:
  - LifeCalendar.exe          (GUI + --headless-update + --startup-check, {PROJECT_VERSION})
  - life_calendar_config.json (default configuration)
  - README.txt                (user guide)
  - uninstall.py              (cleanup helper)
  - windows_automation.py     (task cleanup dependency)

Ready to distribute!

========================================================
"""
        )
    except Exception as exc:
        print(f"\n[FAIL]   Build failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
