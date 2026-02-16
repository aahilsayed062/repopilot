#!/bin/sh
# Startup script for Railway deployment
# Reads PORT from environment and starts uvicorn

PORT_SOURCE=PORT
PORT_VALUE=${PORT}
if [ -z "$PORT_VALUE" ] || echo "$PORT_VALUE" | grep -q '[^0-9]'; then
  for KEY in RAILWAY_PORT RAILWAY_TCP_PORT PORT0 PORT1; do
    VALUE=$(eval echo \$$KEY)
    if [ -n "$VALUE" ] && echo "$VALUE" | grep -q '^[0-9]\+$'; then
      PORT_SOURCE=$KEY
      PORT_VALUE=$VALUE
      break
    fi
    if [ -n "$VALUE" ]; then
      NUM=$(echo "$VALUE" | sed -n 's/[^0-9]*\([0-9]\+\).*/\1/p')
      if [ -n "$NUM" ]; then
        PORT_SOURCE=$KEY
        PORT_VALUE=$NUM
        break
      fi
    fi
  done
fi
PORT_VALUE=${PORT_VALUE:-8000}
echo "Starting uvicorn on port $PORT_VALUE (from $PORT_SOURCE=$PORT_VALUE)"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT_VALUE"
