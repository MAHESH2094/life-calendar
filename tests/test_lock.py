"""
Tests for lock file handling in wallpaper_engine.py
Covers PID validation, stale lock detection, and race conditions.
"""

import os
import sys
import json
import threading
import pytest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def temp_dir(tmp_path):
    """Change CWD to temp dir and restore after."""
    cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(cwd)


class TestLockFileHandling:
    """Test acquire_lock and release_lock functions."""

    def test_acquire_lock_first_time(self, temp_dir):
        """First lock acquisition should succeed."""
        from wallpaper_engine import acquire_lock, release_lock

        # Patch LOCK_FILE to use our temp directory
        lock_path = temp_dir / ".life_calendar.lock"
        with patch("wallpaper_engine.LOCK_FILE", str(lock_path)):
            acquire_lock()
            assert lock_path.exists()
            # Verify lock metadata contains current PID
            content = lock_path.read_text(encoding="utf-8").strip()
            payload = json.loads(content)
            assert payload["pid"] == os.getpid()
            release_lock()
            assert not lock_path.exists()

    def test_acquire_lock_duplicate_fails(self, temp_dir):
        """Trying to acquire lock twice should raise RuntimeError."""
        from wallpaper_engine import acquire_lock, release_lock

        lock_path = temp_dir / ".life_calendar.lock"
        with patch("wallpaper_engine.LOCK_FILE", str(lock_path)):
            acquire_lock()

            # Second acquisition should fail
            with pytest.raises(RuntimeError, match="Another LifeCalendar process"):
                acquire_lock()

            release_lock()

    def test_stale_lock_cleanup(self, temp_dir):
        """Lock owned by dead PID should be cleaned up automatically."""
        from wallpaper_engine import acquire_lock, release_lock
        import time

        lock_path = temp_dir / ".life_calendar.lock"
        with patch("wallpaper_engine.LOCK_FILE", str(lock_path)):
            # Create a stale lock file (old PID, old timestamp)
            stale_pid = 99999  # Non-existent PID
            lock_path.write_text(str(stale_pid))

            # Keep an old timestamp to validate age logging paths.
            old_time = time.time() - (3 * 3600)
            os.utime(lock_path, (old_time, old_time))

            # Mock _is_process_running to always return False for old pid
            with patch("wallpaper_engine._is_process_running", return_value=False):
                # This should clean up the stale lock
                acquire_lock()
                assert lock_path.exists()
                release_lock()

    def test_corrupted_lock_file_cleaned(self, temp_dir):
        """Corrupted lock file (non-numeric PID) should be removed and lock acquired."""
        from wallpaper_engine import acquire_lock, release_lock

        lock_path = temp_dir / ".life_calendar.lock"
        with patch("wallpaper_engine.LOCK_FILE", str(lock_path)):
            # Write garbage to lock file
            lock_path.write_text("not_a_pid")

            # Should clean up and acquire successfully
            acquire_lock()
            assert lock_path.exists()
            payload = json.loads(lock_path.read_text(encoding="utf-8").strip())
            assert payload["pid"] == os.getpid()
            release_lock()

    def test_release_lock_when_missing(self, temp_dir):
        """release_lock should not crash if lock file doesn't exist."""
        from wallpaper_engine import release_lock

        lock_path = temp_dir / ".life_calendar.lock"
        with patch("wallpaper_engine.LOCK_FILE", str(lock_path)):
            # Lock doesn't exist - should not raise
            release_lock()  # Should succeed silently

    def test_concurrent_acquire_only_one_process_wins(self, temp_dir):
        """Concurrent acquire attempts should allow exactly one winner."""
        from wallpaper_engine import acquire_lock, release_lock

        lock_path = temp_dir / ".life_calendar.lock"
        start_barrier = threading.Barrier(6)
        results: list[str] = []
        errors: list[str] = []
        winners_lock = threading.Lock()

        def worker() -> None:
            start_barrier.wait()
            try:
                acquire_lock()
                with winners_lock:
                    results.append("won")
            except RuntimeError:
                with winners_lock:
                    errors.append("busy")

        with patch("wallpaper_engine.LOCK_FILE", str(lock_path)):
            threads = [threading.Thread(target=worker) for _ in range(5)]
            for t in threads:
                t.start()

            # Release workers at the same time
            start_barrier.wait()

            for t in threads:
                t.join(timeout=5)

            assert len(results) == 1
            assert len(errors) == 4

            # Clean up lock held by the winning thread.
            release_lock()

    def test_force_release_lock_removes_existing_lock(self, temp_dir):
        """force_release_lock should remove lock file even if already present."""
        from wallpaper_engine import acquire_lock, force_release_lock

        lock_path = temp_dir / ".life_calendar.lock"
        with patch("wallpaper_engine.LOCK_FILE", str(lock_path)):
            acquire_lock()
            assert lock_path.exists()
            released = force_release_lock("test cleanup")
            assert released is True
            assert not lock_path.exists()
