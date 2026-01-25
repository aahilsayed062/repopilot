"""
Entrypoint script for Railway deployment.
Reads PORT from environment and starts uvicorn.
"""
import os
import re
import logging
import uvicorn


def _resolve_port() -> tuple[int, str, str]:
    candidates = ("PORT", "RAILWAY_PORT", "RAILWAY_TCP_PORT", "PORT0", "PORT1")
    for key in candidates:
        raw = os.getenv(key)
        if raw and raw.isdigit():
            return int(raw), key, raw
    for key in candidates:
        raw = os.getenv(key)
        if raw:
            match = re.search(r"\d+", raw)
            if match:
                return int(match.group(0)), key, raw
    return 8000, "default", "8000"

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    port, source, raw = _resolve_port()
    logging.info("Starting uvicorn on port %s (from %s=%s)", port, source, raw)
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port
    )
