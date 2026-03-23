#!/bin/bash
# -------------------------------------------------
# Docker entrypoint with graceful shutdown support.
# Handles SIGTERM/SIGINT from `docker compose down`.
# -------------------------------------------------

set -e

DATA_DIR="${LIFECALENDAR_DATA_DIR:-/app/data}"
APP_DIR="/app"

mkdir -p "${DATA_DIR}"

# Seed persistent runtime files on first container start.
if [ ! -f "${DATA_DIR}/life_calendar_config.json" ] && [ -f "${APP_DIR}/life_calendar_config.json" ]; then
    cp "${APP_DIR}/life_calendar_config.json" "${DATA_DIR}/life_calendar_config.json"
fi

if [ ! -f "${DATA_DIR}/daily_checkins.json" ]; then
    printf '{"entries":{}}\n' > "${DATA_DIR}/daily_checkins.json"
fi

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
    python "${APP_DIR}/auto_update.py"
    # Use 'sleep & wait' pattern so signals are caught during sleep
    sleep 60 &
    wait $!
done
