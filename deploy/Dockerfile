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

# Runtime state is stored in /app/data so compose can mount it safely.
ENV LIFECALENDAR_DATA_DIR=/app/data

# Run as non-root user for security
RUN groupadd -g 1000 lifecal && \
    useradd -u 1000 -g lifecal -s /bin/bash lifecal && \
    mkdir -p /app/data && \
    chown -R lifecal:lifecal /app
USER lifecal

# Make entrypoint executable
RUN chmod +x /app/docker-entrypoint.sh

# Use entrypoint script with graceful shutdown support
ENTRYPOINT ["/app/docker-entrypoint.sh"]
