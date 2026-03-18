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

# The container will run the headless updater forever
# (it sleeps until the next midnight internally)
CMD ["python", "auto_update.py"]
