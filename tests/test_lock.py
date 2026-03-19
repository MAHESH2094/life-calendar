"""
Tests for lock file handling in wallpaper_engine.py
Covers PID validation, stale lock detection, and race conditions.
"""

import os
import sys
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
            # Verify PID is in the file
            content = lock_path.read_text().strip()
            assert content == str(os.getpid())
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
        """Lock older than 2 hours should be cleaned up automatically."""
        from wallpaper_engine import acquire_lock, release_lock
        import time

        lock_path = temp_dir / ".life_calendar.lock"
        with patch("wallpaper_engine.LOCK_FILE", str(lock_path)):
            # Create a stale lock file (old PID, old timestamp)
            stale_pid = 99999  # Non-existent PID
            lock_path.write_text(str(stale_pid))

            # Make it old (3 hours)
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
            assert lock_path.read_text().strip() == str(os.getpid())
            release_lock()

    def test_release_lock_when_missing(self, temp_dir):
        """release_lock should not crash if lock file doesn't exist."""
        from wallpaper_engine import release_lock

        lock_path = temp_dir / ".life_calendar.lock"
        with patch("wallpaper_engine.LOCK_FILE", str(lock_path)):
            # Lock doesn't exist - should not raise
            release_lock()  # Should succeed silently
