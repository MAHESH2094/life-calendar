#!/usr/bin/env bash
set -euo pipefail

# FIX: [5] macOS signing helper for app bundles.
APP_PATH="${1:-}"
IDENTITY="${2:-}"

if [[ -z "${APP_PATH}" || -z "${IDENTITY}" ]]; then
  echo "Usage: ./sign_macos.sh <path-to-app> <codesign-identity>"
  exit 1
fi

if [[ ! -e "${APP_PATH}" ]]; then
  echo "App not found: ${APP_PATH}"
  exit 1
fi

codesign --force --deep --options runtime --sign "${IDENTITY}" "${APP_PATH}"

echo "Signed: ${APP_PATH}"
