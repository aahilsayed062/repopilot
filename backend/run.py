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

def _is_port_available(host: str, port: int) -> bool:
    """Check if a port is available before starting uvicorn."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            return True
    except OSError:
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    port, source, raw = _resolve_port()

    # Pre-flight check: fail fast if port is already in use
    # (avoids wasting time on model pre-warming just to crash)
    if not _is_port_available("0.0.0.0", port):
        logging.error(
            "Port %s is already in use. Another RepoPilot instance may be running. "
            "Stop the existing process or set a different PORT environment variable.",
            port,
        )
        raise SystemExit(1)

    logging.info("Starting uvicorn on port %s (from %s=%s)", port, source, raw)
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port
    )
