#!/bin/sh
# Startup script for Railway deployment
# Reads PORT from environment and starts uvicorn

PORT=${PORT:-8000}
case "$PORT" in
  ''|*[!0-9]*) PORT=8000 ;;
esac
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
