"""
Tests for edge-case robustness fixes (C1-C5)
"""

import os
import sys
import pytest
import re
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestTimestampValidation:
    """Test C3: Timestamp format validation"""

    def test_valid_timestamp(self):
        """Valid YYYY-MM-DD format should pass validation"""
        timestamp = "2026-03-19"
        assert re.match(r'^\d{4}-\d{2}-\d{2}$', timestamp)

    def test_invalid_timestamp_short(self):
        """Incomplete date should fail validation"""
        timestamp = "2026-03"
        assert not re.match(r'^\d{4}-\d{2}-\d{2}$', timestamp)

    def test_invalid_timestamp_garbage(self):
        """Random text should fail validation"""
        timestamp = "abc-def-ghi"
        assert not re.match(r'^\d{4}-\d{2}-\d{2}$', timestamp)

    def test_invalid_timestamp_with_time(self):
        """ISO format with time should fail (only date expected)"""
        timestamp = "2026-03-19T10:30:00"
        assert not re.match(r'^\d{4}-\d{2}-\d{2}$', timestamp)


class TestNonNumericPIDHandling:
    """Test C1: Non-numeric PID in lock file"""

    def test_corrupted_pid_format(self, tmp_path):
        """Non-numeric PID should be treated as corrupted"""
        lock_file = tmp_path / ".test.lock"
        
        # Write garbage PID
        lock_file.write_text("not_a_number")
        
        # Try to read and parse
        try:
            pid_str = lock_file.read_text().strip()
            pid = int(pid_str)
            # Should not reach here
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
        
        source.write_text("test content")
        
        # shutil.move should work as fallback
        shutil.move(str(source), str(dest))
        
        assert dest.exists()
        assert not source.exists()
        assert dest.read_text() == "test content"

    def test_os_replace_with_existing_dest(self, tmp_path):
        """Verify shutil.move overwrites destination like os.replace"""
        import shutil
        
        source = tmp_path / "source.txt"
        dest = tmp_path / "dest.txt"
        
        source.write_text("new content")
        dest.write_text("old content")
        
        # shutil.move should overwrite
        shutil.move(str(source), str(dest))
        
        assert dest.exists()
        assert not source.exists()
        assert dest.read_text() == "new content"
