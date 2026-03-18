#!/bin/bash
# -------------------------------------------------
# Docker entrypoint with graceful shutdown support.
# Handles SIGTERM/SIGINT from `docker compose down`.
# -------------------------------------------------

set -e

# Graceful shutdown: exit cleanly on SIGTERM/SIGINT
cleanup() {
    echo "[entrypoint] Received shutdown signal, exiting gracefully..."
    exit 0
}
trap cleanup SIGTERM SIGINT

echo "[entrypoint] Life Calendar Docker container starting..."
echo "[entrypoint] Updates will run every 60 seconds."

# Infinite loop: run auto_update, then sleep.
# The auto_update script only generates a wallpaper when the date has changed,
# so running it frequently has minimal overhead.
while true; do
    python auto_update.py
    # Use 'sleep & wait' pattern so signals are caught during sleep
    sleep 60 &
    wait $!
done
