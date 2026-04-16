"""Compatibility wrapper for the new cross-platform build pipeline."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()


def main() -> None:
    # FIX: [1] Keep legacy entrypoint but delegate to explicit-arch packaging script.
    cmd = [sys.executable, str(BASE_DIR / "build.py"), "--platform", "windows"]
    result = subprocess.run(cmd)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
