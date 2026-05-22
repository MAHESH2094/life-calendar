#!/usr/bin/env bash
# -------------------------------------------------
# Wrapper that can be put into a crontab.
# It ensures we run from the repo root so that relative paths work.
# -------------------------------------------------
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT_DIR}/src:${PYTHONPATH:-}"
cd "${ROOT_DIR}"

python3 -m lifecalendar.auto_update
