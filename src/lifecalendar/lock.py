"""Atomic file locking with PID-based stale detection and crash recovery."""

from __future__ import annotations

import atexit
import json
import logging
import os
import platform
import signal
import sys
import threading
import time
from typing import Any

from .auto_update import get_base_dir

logger = logging.getLogger("WallpaperEngine")

# Lock file lives next to the data directory (config, wallpaper, etc.).
BASE_DIR = str(get_base_dir())
LOCK_FILE = os.path.join(BASE_DIR, ".life_calendar.lock")

DEFAULT_MAX_RUNTIME_MINUTES = 30
STALE_LOCK_TTL_SECONDS = 300
LOCK_ACQUIRE_POLL_SECONDS = 0.25

# Ensure signal hooks are only installed once per process.
_LOCK_SIGNAL_HOOKS_INSTALLED = False


# ── process helpers ────────────────────────────────────────────────────────

def _is_process_running(pid: int) -> bool:
    """Check if a process with given PID is running."""
    if sys.platform == "win32":
        try:
            import ctypes as _ctypes
            kernel32 = _ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except Exception as e:
            logger.debug(f"Could not check process {pid} status: {e}")
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


# ── lock metadata ──────────────────────────────────────────────────────────

def _get_lock_max_age_seconds() -> int:
    """Return max lock age in seconds, configurable via env var."""
    value = os.getenv("LIFECALENDAR_MAX_RUNTIME_MINUTES")
    if value:
        try:
            minutes = int(value)
            if minutes > 0:
                return minutes * 60
        except ValueError:
            logger.warning(
                "Invalid LIFECALENDAR_MAX_RUNTIME_MINUTES=%s, using default %s",
                value,
                DEFAULT_MAX_RUNTIME_MINUTES,
            )
    return DEFAULT_MAX_RUNTIME_MINUTES * 60


def _read_lock_info() -> dict[str, Any]:
    """Read lock metadata from disk.

    Supports both legacy lock files (PID as plain text) and JSON metadata.
    """
    with open(LOCK_FILE, "r", encoding="utf-8") as file_handle:
        raw = file_handle.read().strip()

    # Legacy format: plain PID
    if raw.isdigit():
        return {"pid": int(raw), "format": "legacy"}

    # Current format: JSON
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Lock payload must be an object")
    return payload


def _write_lock_info(fd: int) -> None:
    """Write JSON lock metadata to an already-created lock file descriptor."""
    payload = {
        "pid": os.getpid(),
        "created_at": time.time(),
        "host": platform.node() or "unknown",
        "version": 1,
    }
    os.write(fd, json.dumps(payload, separators=(",", ":")).encode("utf-8"))


def _remove_lock_file(reason: str) -> None:
    """Remove lock file and log the reason."""
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
            logger.warning("Removed lock file: %s", reason)
    except OSError as exc:
        logger.warning("Failed to remove lock file (%s): %s", reason, exc)


# ── signal / exit hooks ────────────────────────────────────────────────────

def install_lock_signal_handlers() -> None:
    """Install signal and exit hooks so locks are cleaned up on termination."""
    global _LOCK_SIGNAL_HOOKS_INSTALLED
    if _LOCK_SIGNAL_HOOKS_INSTALLED:
        return

    if threading.current_thread() is not threading.main_thread():
        return

    def _handle_exit_signal(signum: int, _frame: Any) -> None:
        logger.warning("Received signal %s, releasing lock", signum)
        release_lock()
        raise SystemExit(128 + signum)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _handle_exit_signal)
        except (ValueError, OSError):
            continue

    atexit.register(release_lock)
    _LOCK_SIGNAL_HOOKS_INSTALLED = True


# ── public API ─────────────────────────────────────────────────────────────

def force_release_lock(reason: str = "manual force release") -> bool:
    """Force-remove lock file for recovery operations."""
    if os.path.exists(LOCK_FILE):
        _remove_lock_file(reason)
        return True
    return False


def acquire_lock(timeout_seconds: float = 0) -> None:
    """Acquire exclusive lock with PID verification and stale detection."""
    install_lock_signal_handlers()

    start_time = time.monotonic()
    last_error_message = "Another LifeCalendar process is already running"

    while True:
        # Create new lock atomically first (fast path).
        try:
            fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            try:
                _write_lock_info(fd)
            finally:
                os.close(fd)
            logger.info("Lock acquired (PID: %s)", os.getpid())
            return
        except FileExistsError:
            pass
        except OSError as exc:
            logger.error("Failed to create lock file: %s", exc)
            raise RuntimeError(f"Cannot create lock file (permission issue or read-only directory): {exc}") from exc

        # Slow path: inspect and decide whether existing lock is stale.
        try:
            lock_info = _read_lock_info()
            raw_pid = lock_info.get("pid")
            if raw_pid is None:
                _remove_lock_file("lock file missing pid field")
                continue
            lock_pid = int(raw_pid)
            lock_age_seconds = max(0.0, time.time() - os.path.getmtime(LOCK_FILE))
            max_age_seconds = _get_lock_max_age_seconds()

            if not _is_process_running(lock_pid):
                if lock_age_seconds > STALE_LOCK_TTL_SECONDS:
                    _remove_lock_file(
                        f"stale lock from dead process PID {lock_pid} (age {lock_age_seconds:.1f}s)"
                    )
                    continue
                last_error_message = (
                    "Another LifeCalendar process is already running "
                    f"(dead PID: {lock_pid}, age: {lock_age_seconds:.0f}s, waiting for stale TTL)."
                )
            elif lock_age_seconds > max_age_seconds:
                last_error_message = (
                    "Another LifeCalendar process is already running "
                    f"(PID: {lock_pid}, age: {lock_age_seconds / 60:.0f}m, "
                    f"max_runtime: {max_age_seconds / 60:.0f}m)."
                )
            else:
                last_error_message = (
                    "Another LifeCalendar process is already running "
                    f"(PID: {lock_pid}, age: {lock_age_seconds / 60:.0f}m)."
                )

        except (ValueError, TypeError, json.JSONDecodeError, OSError) as exc:
            _remove_lock_file(f"corrupted or unreadable lock ({exc})")
            continue

        if timeout_seconds <= 0:
            raise RuntimeError(last_error_message)

        elapsed = time.monotonic() - start_time
        if elapsed >= timeout_seconds:
            raise RuntimeError(
                f"Timed out after {timeout_seconds:.0f}s waiting for lock. {last_error_message}"
            )

        time.sleep(LOCK_ACQUIRE_POLL_SECONDS)


def release_lock() -> None:
    """Release lock file owned by current process.

    Legacy lock files (plain PID text) are also supported for cleanup.
    """
    try:
        try:
            lock_info = _read_lock_info()
        except FileNotFoundError:
            return
        except (ValueError, json.JSONDecodeError, OSError):
            try:
                os.remove(LOCK_FILE)
            except OSError:
                pass
            return

        raw_pid = lock_info.get("pid")
        if raw_pid is None:
            _remove_lock_file("lock file missing pid field")
            return

        try:
            lock_pid = int(raw_pid)
        except (ValueError, TypeError):
            _remove_lock_file(f"lock file has non-numeric pid: {raw_pid!r}")
            return

        if lock_pid == os.getpid():
            os.remove(LOCK_FILE)
            logger.info("Lock released (PID: %s)", os.getpid())
        else:
            logger.debug(
                "Skipping lock release because owner PID %s != current PID %s",
                lock_pid,
                os.getpid(),
            )
    except Exception as exc:
        logger.debug(f"Could not clean up lock file: {exc}")
