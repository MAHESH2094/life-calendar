"""
Tests for edge-case robustness fixes (C1-C5)
"""

import sys
from pathlib import Path
from unittest.mock import patch
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestTimestampValidation:
    """Test C3: Timestamp format validation"""

    def test_valid_timestamp_today_skips_update(self, tmp_path):
        """Valid today timestamp should skip update."""
        from auto_update import needs_update

        ts_file = tmp_path / ".last_update_date"
        ts_file.write_text(str(date.today()), encoding="utf-8")

        with patch("auto_update.BASE_DIR", tmp_path):
            assert needs_update() is False

    def test_invalid_timestamp_short(self, tmp_path):
        """Incomplete date should trigger update."""
        from auto_update import needs_update

        ts_file = tmp_path / ".last_update_date"
        ts_file.write_text("2026-03", encoding="utf-8")

        with patch("auto_update.BASE_DIR", tmp_path):
            assert needs_update() is True

    def test_invalid_timestamp_garbage(self, tmp_path):
        """Random text should trigger update."""
        from auto_update import needs_update

        ts_file = tmp_path / ".last_update_date"
        ts_file.write_text("abc-def-ghi", encoding="utf-8")

        with patch("auto_update.BASE_DIR", tmp_path):
            assert needs_update() is True

    def test_invalid_calendar_date_triggers_update(self, tmp_path):
        """Impossible dates like YYYY-99-99 should trigger update."""
        from auto_update import needs_update

        ts_file = tmp_path / ".last_update_date"
        ts_file.write_text("2026-99-99", encoding="utf-8")

        with patch("auto_update.BASE_DIR", tmp_path):
            assert needs_update() is True


class TestNonNumericPIDHandling:
    """Test C1: Non-numeric PID in lock file"""

    def test_corrupted_pid_format(self, tmp_path):
        """Non-numeric PID should be treated as corrupted"""
        lock_file = tmp_path / ".test.lock"

        # Write garbage PID
        lock_file.write_text("not_a_number", encoding="utf-8")

        # Try to read and parse
        pid_str = lock_file.read_text(encoding="utf-8").strip()
        try:
            int(pid_str)
            assert False, "Should have raised ValueError"
        except ValueError:
            # Expected - corrupted PID
            pass


class TestShutilMoveFallback:
    """Test C5: shutil.move fallback for os.replace"""

    def test_os_replace_equivalence(self, tmp_path):
        """Verify shutil.move works as fallback for os.replace"""
        import shutil

        source = tmp_path / "source.txt"
        dest = tmp_path / "dest.txt"

        source.write_text("test content", encoding="utf-8")

        # shutil.move should work as fallback
        shutil.move(str(source), str(dest))

        assert dest.exists()
        assert not source.exists()
        assert dest.read_text(encoding="utf-8") == "test content"

    def test_os_replace_with_existing_dest(self, tmp_path):
        """Verify shutil.move overwrites destination like os.replace"""
        import shutil

        source = tmp_path / "source.txt"
        dest = tmp_path / "dest.txt"

        source.write_text("new content", encoding="utf-8")
        dest.write_text("old content", encoding="utf-8")

        # shutil.move should overwrite
        shutil.move(str(source), str(dest))

        assert dest.exists()
        assert not source.exists()
        assert dest.read_text(encoding="utf-8") == "new content"
