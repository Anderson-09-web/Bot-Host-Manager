#!/bin/bash
# Discord Bot Hosting Panel — API server startup script
# Note: Python packages are pre-installed via Replit package management
set -e

cd "$(dirname "$0")"

echo "=== Starting Discord Bot Hosting Panel API on port ${PORT:-8080} ==="
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8080}" \
  --reload \
  --log-level info \
  --access-log
