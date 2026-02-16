"""
Structured logging with request_id tracking.
"""

import structlog
import logging
import sys
from uuid import uuid4
from contextvars import ContextVar

# Context variable for request tracking
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="no-request")


def get_request_id() -> str:
    """Get current request ID from context."""
    return request_id_ctx.get()


def set_request_id(request_id: str | None = None) -> str:
    """Set request ID in context. Generates one if not provided."""
    rid = request_id or str(uuid4())[:8]
    request_id_ctx.set(rid)
    return rid


def add_request_id(logger, method_name, event_dict):
    """Processor to add request_id to all log entries."""
    event_dict["request_id"] = get_request_id()
    return event_dict


def setup_logging(debug: bool = False):
    """Configure structured logging for the application."""
    # Ensure console logging can print any unicode from repositories/errors on Windows.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    # Set log level
    log_level = logging.DEBUG if debug else logging.INFO
    
    stdout_encoding = (getattr(sys.stdout, "encoding", None) or "").lower()
    use_console_renderer = debug and ("utf" in stdout_encoding)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            add_request_id,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if use_console_renderer else structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Also configure standard logging for third-party libs
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )
    # Reduce per-request transport noise while keeping warnings/errors visible.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)
