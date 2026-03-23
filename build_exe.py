"""Build the single-file Windows package for Life Calendar."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

from daily_companion import merge_config

PROJECT_VERSION = "3.0.0"
BASE_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = BASE_DIR / "LifeCalendar_Package"
DIST_DIR = BASE_DIR / "dist"
BUILD_DIR = BASE_DIR / "build"


def get_hidden_imports() -> list[str]:
    """Dynamically extract hidden imports from requirements.txt.

    Returns a list of --hidden-import=module flags for modules that
    need explicit importing during bundling.
    """
    hidden_import_modules = {
        "pillow": "PIL",           # Package pillow imports as PIL
        "screeninfo": "screeninfo", # Direct mapping
        "auto_update": "auto_update",  # Local module
    }

    requirements_file = BASE_DIR / "requirements.txt"
    flags = []

    if not requirements_file.exists():
        # Fallback to hardcoded defaults if requirements.txt missing
        return [f"--hidden-import={module}" for module in hidden_import_modules.values()]

    try:
        with open(requirements_file, 'r') as f:
            for line in f:
                line = line.strip().split('#')[0].strip()  # Remove comments
                if not line:
                    continue

                # Parse package name (before == or other operators)
                package_name = line.split('==')[0].split('>=')[0].split('<=')[0].split('>')[0].split('<')[0].strip()

                # Check if this package needs a hidden import
                import_name = hidden_import_modules.get(package_name.lower())
                if import_name:
                    flags.append(f"--hidden-import={import_name}")
    except Exception as e:
        print(f"[WARN]   Could not read requirements.txt: {e}")
        # Fallback to hardcoded
        return [f"--hidden-import={module}" for module in hidden_import_modules.values()]

    return flags


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
    hidden_imports = get_hidden_imports()

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
        *hidden_imports,
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

    config_src = BASE_DIR / "life_calendar_config.json"
    config_dst = OUTPUT_DIR / "life_calendar_config.json"
    if config_src.exists():
        shutil.copy(config_src, config_dst)
        print("[OK]     Copied life_calendar_config.json")
    else:
        config_dst.write_text(json.dumps(merge_config(), indent=2), encoding="utf-8")
        print("[OK]     Generated default life_calendar_config.json")

    for filename in ("README.txt", "uninstall.py", "windows_automation.py"):
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
