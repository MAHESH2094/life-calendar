"""OS-specific wallpaper setting implementations."""

from __future__ import annotations

import ctypes
import logging
import os
import shutil
import subprocess
import sys
from typing import Tuple

logger = logging.getLogger("WallpaperEngine")


def set_windows_wallpaper(wallpaper_path: str) -> Tuple[bool, str]:
    """Set wallpaper on Windows with verification and broadcast refresh."""
    abs_path = os.path.abspath(wallpaper_path)

    if not os.path.isfile(abs_path):
        return False, "Wallpaper file missing"

    if os.path.getsize(abs_path) < 1000:
        return False, "Wallpaper file corrupted (too small)"

    result = ctypes.windll.user32.SystemParametersInfoW(20, 0, abs_path, 3)

    if not result:
        return False, "Windows API call failed"

    try:
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, 0, SMTO_ABORTIFHUNG, 5000, None
        )
    except Exception as e:
        logger.debug(f"Could not broadcast wallpaper change notification: {e}")

    return True, "Wallpaper set successfully"


def set_macos_wallpaper(wallpaper_path: str) -> Tuple[bool, str]:
    """Set wallpaper on macOS using osascript args for robust path handling."""
    abs_path = os.path.abspath(wallpaper_path)
    try:
        script = (
            "on run argv\n"
            "set wallpaperPath to quoted form of POSIX path of (item 1 of argv)\n"
            "tell application \"System Events\"\n"
            "repeat with d in desktops\n"
            "set picture of d to POSIX file wallpaperPath as text\n"
            "end repeat\n"
            "end tell\n"
            "end run"
        )
        result = subprocess.run(["osascript", "-e", script, abs_path], capture_output=True, text=True)

        if result.returncode == 0:
            logger.info("Wallpaper set successfully on macOS")
            return True, "Wallpaper set successfully"
        else:
            logger.error(f"osascript failed: {result.stderr}")
            return False, "osascript failed"

    except Exception as e:
        logger.exception(f"Failed to set macOS wallpaper: {e}")
        return False, f"Failed to set macOS wallpaper: {str(e)[:100]}"


def set_linux_wallpaper(wallpaper_path: str) -> Tuple[bool, str]:
    """Set wallpaper on Linux with multi-DE support and fallback strategies."""
    de = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
    session = os.environ.get('DESKTOP_SESSION', '').lower()

    desktop_env = (de or session).lower()

    if desktop_env:
        logger.info(
            f"Detected Linux desktop: XDG_CURRENT_DESKTOP={os.environ.get('XDG_CURRENT_DESKTOP', 'unknown')}, "
            f"DESKTOP_SESSION={os.environ.get('DESKTOP_SESSION', 'unknown')}"
        )
    else:
        logger.info("No desktop environment detected - will try fallback methods")

    abs_path = os.path.abspath(wallpaper_path)

    try:
        success = False
        command_used = None

        if 'gnome' in desktop_env or 'ubuntu' in desktop_env or 'unity' in desktop_env:
            if not shutil.which("gsettings"):
                logger.error("gsettings not installed (required for GNOME/Ubuntu)")
                return False, "gsettings not installed"

            command_used = "gsettings"
            r1 = subprocess.run(
                ['gsettings', 'set', 'org.gnome.desktop.background', 'picture-uri', f'file://{abs_path}'],
                capture_output=True,
            )
            r2 = subprocess.run(
                ['gsettings', 'set', 'org.gnome.desktop.background', 'picture-uri-dark', f'file://{abs_path}'],
                capture_output=True,
            )
            success = r1.returncode == 0 or r2.returncode == 0

        elif 'kde' in desktop_env or 'plasma' in desktop_env:
            if not shutil.which("plasma-apply-wallpaperimage"):
                logger.error("plasma-apply-wallpaperimage not installed (required for KDE)")
                return False, "plasma-apply-wallpaperimage not installed"

            command_used = "plasma-apply-wallpaperimage"
            result = subprocess.run(['plasma-apply-wallpaperimage', abs_path], capture_output=True)
            success = result.returncode == 0

        elif 'xfce' in desktop_env:
            if not shutil.which("xfconf-query"):
                logger.error("xfconf-query not installed (required for XFCE)")
                return False, "xfconf-query not installed"

            command_used = "xfconf-query"
            result = subprocess.run(
                ['xfconf-query', '-c', 'xfce4-desktop', '-p',
                 '/backdrop/screen0/monitor0/image-path', '-s', abs_path],
                capture_output=True,
            )
            success = result.returncode == 0

        elif 'mate' in desktop_env:
            if not shutil.which("gsettings"):
                logger.error("gsettings not installed (required for MATE)")
                return False, "gsettings not installed"

            command_used = "gsettings"
            result = subprocess.run(
                ['gsettings', 'set', 'org.mate.background', 'picture-filename', abs_path],
                capture_output=True,
            )
            success = result.returncode == 0

        elif 'cinnamon' in desktop_env:
            if not shutil.which("gsettings"):
                logger.error("gsettings not installed (required for Cinnamon)")
                return False, "gsettings not installed"

            command_used = "gsettings"
            result = subprocess.run(
                ['gsettings', 'set', 'org.cinnamon.desktop.background', 'picture-uri', f'file://{abs_path}'],
                capture_output=True,
            )
            success = result.returncode == 0

        else:
            if shutil.which("xwallpaper"):
                logger.info("Trying xwallpaper fallback")
                command_used = "xwallpaper"
                result = subprocess.run(['xwallpaper', '--zoom', abs_path], capture_output=True)
                success = result.returncode == 0

            if not success and shutil.which("feh"):
                logger.info("Trying feh (window manager fallback)")
                command_used = "feh"
                result = subprocess.run(['feh', '--bg-scale', abs_path], capture_output=True)
                success = result.returncode == 0

            if not success and shutil.which("nitrogen"):
                logger.info("Trying nitrogen fallback")
                command_used = "nitrogen"
                result = subprocess.run(
                    ['nitrogen', '--set-zoom-fill', '--save', abs_path], capture_output=True,
                )
                success = result.returncode == 0

            if not success:
                logger.error(
                    "No supported wallpaper method found. "
                    "Install one of: xwallpaper, feh, nitrogen, or a supported desktop environment"
                )
                return False, "No supported wallpaper command found"

        if success:
            logger.info(f"Wallpaper set successfully on Linux using {command_used}")
            return True, "Wallpaper set successfully"
        else:
            logger.error(f"Wallpaper command '{command_used}' failed. DE: {desktop_env}")
            return False, f"Wallpaper command '{command_used}' failed"

    except Exception as e:
        logger.exception(f"Failed to set wallpaper on Linux: {e}")
        return False, f"Failed to set wallpaper on Linux: {str(e)[:100]}"


def set_wallpaper(wallpaper_path: str) -> Tuple[bool, str]:
    """Set wallpaper using the appropriate OS-specific method."""
    try:
        if sys.platform == 'win32':
            return set_windows_wallpaper(wallpaper_path)
        elif sys.platform == 'darwin':
            return set_macos_wallpaper(wallpaper_path)
        elif sys.platform.startswith('linux'):
            return set_linux_wallpaper(wallpaper_path)
        else:
            return False, f"Unsupported OS: {sys.platform}"
    except (OSError, ValueError) as e:
        logger.exception(f"Failed to set wallpaper: {e}")
        return False, f"Failed to set wallpaper: {str(e)[:100]}"
