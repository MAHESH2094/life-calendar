# -------------------------------------------------
# Multi‑stage build: first stage installs deps, second stage runs the updater
# -------------------------------------------------
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY . /app

# The container will continuously run the updater.
# The auto_update script only generates a wallpaper when the date has changed,
# so running it frequently has minimal overhead. This keeps the container alive
# and ensures responsive updates even if dates change during container uptime.
CMD ["bash","-c","while true; do python auto_update.py; sleep 60; done"]
