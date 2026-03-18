#!/usr/bin/env bash
# -------------------------------------------------
# Wrapper that can be put into a crontab.
# It ensures we run from the repo root so that relative paths work.
# -------------------------------------------------
cd "$(dirname "$(realpath "$0")")"
python auto_update.py
