#!/usr/bin/env python3
"""Post-build smoke checks for Life Calendar artifacts."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).parent.resolve()
BLOCKERS: List[str] = []


def _check_file(path: Path, min_size: int = 1_000_000) -> None:
    if not path.exists():
        BLOCKERS.append(f"Missing artifact: {path}")
        return
    size = path.stat().st_size
    if size < min_size:
        BLOCKERS.append(f"Artifact too small ({size} bytes): {path}")


def _smoke_run(executable: Path, args: list[str]) -> None:
    if not executable.exists():
        return
    try:
        subprocess.run([str(executable), *args], timeout=20, capture_output=True, text=True)
    except Exception as exc:
        BLOCKERS.append(f"Smoke run failed for {executable}: {exc}")


def run_checks() -> int:
    windows_x64 = BASE_DIR / "dist" / "windows" / "x64" / "LifeCalendar.exe"
    windows_x86 = BASE_DIR / "dist" / "windows" / "x86" / "LifeCalendar.exe"
    linux_bin = BASE_DIR / "dist" / "linux" / "LifeCalendar"
    macos_app = BASE_DIR / "dist" / "macos" / "LifeCalendar.app"

    # FIX: [4] Validate expected outputs for each platform target.
    _check_file(windows_x64)
    _check_file(windows_x86)
    _check_file(linux_bin, min_size=500_000)
    if not macos_app.exists():
        BLOCKERS.append(f"Missing artifact: {macos_app}")

    # Smoke tests use CLI-like invocation paths when available.
    _smoke_run(windows_x64, ["--headless-update", "--dry-run"])
    _smoke_run(windows_x86, ["--headless-update", "--dry-run"])
    _smoke_run(linux_bin, ["--headless-update", "--dry-run"])

    if BLOCKERS:
        print("=== RELEASE CHECK BLOCKERS ===")
        for blocker in BLOCKERS:
            print(f"- {blocker}")
        return 1

    print("Release check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_checks())
