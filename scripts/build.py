#!/usr/bin/env python3
"""Universal Life Calendar packaging entrypoint."""

from __future__ import annotations

import argparse
import os
import platform
import struct
import subprocess
import sys
from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).parent.resolve()
SPEC_FILE = BASE_DIR / "life_calendar.spec"
BLOCKERS: List[str] = []


def _python_bits() -> int:
    return struct.calcsize("P") * 8


def _run_pyinstaller(target: str, arch: str, dist_dir: Path, work_dir: Path) -> bool:
    env = os.environ.copy()
    env["LIFECALENDAR_TARGET_ARCH"] = arch

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(work_dir),
        str(SPEC_FILE),
    ]

    # FIX: [2] Try explicit target-arch first; fallback when spec-mode rejects it.
    cmd_with_target = [*cmd[:-1], f"--target-arch={arch}", cmd[-1]]

    print(f"[BUILD] target={target} arch={arch}")
    try:
        subprocess.run(
            cmd_with_target,
            check=True,
            cwd=str(BASE_DIR),
            env=env,
            capture_output=True,
            text=True,
        )
        print(f"[OK] {target} {arch} build complete -> {dist_dir}")
        return True
    except subprocess.CalledProcessError as exc:
        message = f"{exc.stdout or ''}\n{exc.stderr or ''}\n{exc}"
        if "makespec options not valid when a .spec file is given" not in message:
            BLOCKERS.append(f"{target} {arch}: pyinstaller failed ({exc})")
            print(f"[WARN] {target} {arch} failed")
            if exc.stdout:
                print(exc.stdout)
            if exc.stderr:
                print(exc.stderr)
            return False

    try:
        # FIX: [2] Retry without target-arch when spec-mode forbids CLI arch option.
        subprocess.run(cmd, check=True, cwd=str(BASE_DIR), env=env)
        BLOCKERS.append(
            f"{target} {arch}: pyinstaller rejected --target-arch with .spec; used env-driven target_arch fallback."
        )
        print(f"[OK] {target} {arch} build complete via fallback -> {dist_dir}")
        return True
    except subprocess.CalledProcessError as exc:
        BLOCKERS.append(f"{target} {arch}: pyinstaller failed ({exc})")
        print(f"[WARN] {target} {arch} failed")
        return False


def _build_windows() -> None:
    machine = platform.machine().lower()
    python_bits = _python_bits()

    # FIX: [3] Verify builder interpreter architecture and report mismatch risk.
    print(f"[INFO] Windows host machine={machine} python_bits={python_bits}")

    # Priority 1: x64 build
    _run_pyinstaller(
        target="windows",
        arch="x86_64",
        dist_dir=BASE_DIR / "dist" / "windows" / "x64",
        work_dir=BASE_DIR / "build" / "windows" / "x64",
    )

    # Priority 2: x86 build
    # PyInstaller generally requires a 32-bit Python interpreter to build 32-bit binaries.
    if python_bits != 32:
        BLOCKERS.append(
            "windows x86: skipped because current interpreter is not 32-bit CPython. "
            "Use a 32-bit Python on Windows to build x86 binaries."
        )
        return

    _run_pyinstaller(
        target="windows",
        arch="x86",
        dist_dir=BASE_DIR / "dist" / "windows" / "x86",
        work_dir=BASE_DIR / "build" / "windows" / "x86",
    )


def _build_macos() -> None:
    machine = platform.machine().lower()
    if "x86_64" not in machine and "amd64" not in machine:
        BLOCKERS.append(
            f"macos x86_64: host machine is '{machine}'. Native x86_64 artifact may require Rosetta or x86_64 runner."
        )
    _run_pyinstaller(
        target="macos",
        arch="x86_64",
        dist_dir=BASE_DIR / "dist" / "macos",
        work_dir=BASE_DIR / "build" / "macos",
    )


def _build_linux() -> None:
    _run_pyinstaller(
        target="linux",
        arch="x86_64",
        dist_dir=BASE_DIR / "dist" / "linux",
        work_dir=BASE_DIR / "build" / "linux",
    )


def print_blocker_report() -> None:
    print("\n=== BLOCKERS REPORT ===")
    if not BLOCKERS:
        print("No blockers collected.")
        return
    for blocker in BLOCKERS:
        print(f"- {blocker}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-platform PyInstaller build entrypoint")
    parser.add_argument(
        "--platform",
        choices=["auto", "windows", "linux", "macos", "all"],
        default="auto",
        help="Build target selection",
    )
    args = parser.parse_args()

    if not SPEC_FILE.exists():
        print(f"[FAIL] Missing spec file: {SPEC_FILE}")
        return 1

    target = args.platform
    if target == "auto":
        if sys.platform == "win32":
            target = "windows"
        elif sys.platform == "darwin":
            target = "macos"
        elif sys.platform.startswith("linux"):
            target = "linux"
        else:
            BLOCKERS.append(f"Unsupported host platform: {sys.platform}")
            print_blocker_report()
            return 0

    if target in {"windows", "all"}:
        _build_windows()
    if target in {"linux", "all"}:
        _build_linux()
    if target in {"macos", "all"}:
        _build_macos()

    print_blocker_report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
