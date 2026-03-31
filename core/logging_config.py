"""Structured logging configuration with JSON support and request correlation."""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
import uuid
from contextvars import ContextVar
from typing import Any, Final

# Context variables for request correlation
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
book_id_var: ContextVar[str | None] = ContextVar("book_id", default=None)
job_id_var: ContextVar[str | None] = ContextVar("job_id", default=None)

# Module-level lock for thread-safe operations
_lock: threading.Lock = threading.Lock()


class JSONLogFormatter(logging.Formatter):
    """JSON formatter for structured logging in production."""

    def __init__(
        self,
        *,
        fmt: str | None = None,
        datefmt: str | None = None,
        style: str = "%",
        validate: bool = True,
    ):
        super().__init__(fmt=fmt, datefmt=datefmt, style=style, validate=validate)

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: dict[str, Any] = {
            "timestamp": time.strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime(record.created)
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add request correlation context
        request_id = request_id_var.get()
        if request_id:
            log_data["request_id"] = request_id

        user_id = user_id_var.get()
        if user_id:
            log_data["user_id"] = user_id

        book_id = book_id_var.get()
        if book_id:
            log_data["book_id"] = book_id

        job_id = job_id_var.get()
        if job_id:
            log_data["job_id"] = job_id

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from the record
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "getMessage",
            }:
                log_data[key] = value

        # Add source location
        log_data["source"] = {
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName,
        }

        return json.dumps(log_data, ensure_ascii=False, separators=(",", ":"))


class ColoredConsoleFormatter(logging.Formatter):
    """Colored formatter for development environments."""

    COLORS: Final[dict[str, str]] = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET: Final[str] = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format with colors for terminal output."""
        color = self.COLORS.get(record.levelname, "")
        reset = self.RESET if color else ""

        # Build context string
        context_parts = []
        request_id = request_id_var.get()
        if request_id:
            context_parts.append(f"rid={request_id[:8]}")

        user_id = user_id_var.get()
        if user_id:
            context_parts.append(f"uid={user_id[:8]}")

        book_id = book_id_var.get()
        if book_id:
            context_parts.append(f"bid={book_id[:8]}")

        job_id = job_id_var.get()
        if job_id:
            context_parts.append(f"jid={job_id[:8]}")

        context_str = f" [{', '.join(context_parts)}]" if context_parts else ""

        return (
            f"{color}{record.levelname:8}{reset} | "
            f"{time.strftime('%H:%M:%S', time.localtime(record.created))} | "
            f"{record.name:20}{context_str} | "
            f"{record.getMessage()}"
        )


def generate_request_id() -> str:
    """Generate a unique request ID."""
    return uuid.uuid4().hex[:16]


def set_request_id(request_id: str | None = None) -> str:
    """Set the request ID for the current context."""
    rid = request_id or generate_request_id()
    request_id_var.set(rid)
    return rid


def get_request_id() -> str:
    """Get the current request ID."""
    return request_id_var.get()


def set_user_id(user_id: str | None) -> None:
    """Set the user ID for the current context."""
    user_id_var.set(user_id)


def get_user_id() -> str | None:
    """Get the current user ID."""
    return user_id_var.get()


def set_book_id(book_id: str | None) -> None:
    """Set the book ID for the current context."""
    book_id_var.set(book_id)


def get_book_id() -> str | None:
    """Get the current book ID."""
    return book_id_var.get()


def set_job_id(job_id: str | None) -> None:
    """Set the job ID for the current context."""
    job_id_var.set(job_id)


def get_job_id() -> str | None:
    """Get the current job ID."""
    return job_id_var.get()


def clear_context() -> None:
    """Clear all context variables."""
    request_id_var.set("")
    user_id_var.set(None)
    book_id_var.set(None)
    job_id_var.set(None)


def configure_logging(
    *,
    level: str | None = None,
    json_format: bool | None = None,
    enable_context: bool = True,
) -> None:
    """Configure structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR). Defaults to env LOG_LEVEL.
        json_format: Use JSON formatting for production. Auto-detected from ENVIRONMENT.
        enable_context: Enable request correlation context.
    """
    # Determine log level
    log_level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()

    # Determine format (JSON for production, colored for development)
    is_production = os.getenv("ENVIRONMENT", "development").lower() in (
        "production",
        "prod",
    )
    use_json = json_format if json_format is not None else is_production

    # Create formatter
    if use_json:
        formatter: logging.Formatter = JSONLogFormatter()
    else:
        formatter = ColoredConsoleFormatter()

    # Configure root handler
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, log_level, logging.INFO))
    root_logger.addHandler(console_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Log configuration
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured: level=%s, format=%s",
        log_level,
        "JSON" if use_json else "colored",
    )


class LogContext:
    """Context manager for temporary log context."""

    def __init__(
        self,
        *,
        request_id: str | None = None,
        user_id: str | None = None,
        book_id: str | None = None,
        job_id: str | None = None,
    ):
        self.request_id = request_id
        self.user_id = user_id
        self.book_id = book_id
        self.job_id = job_id
        self._tokens: dict[str, Any] = {}

    def __enter__(self) -> "LogContext":
        """Enter context and set variables."""
        if self.request_id is not None:
            self._tokens["request_id"] = request_id_var.set(self.request_id)
        if self.user_id is not None:
            self._tokens["user_id"] = user_id_var.set(self.user_id)
        if self.book_id is not None:
            self._tokens["book_id"] = book_id_var.set(self.book_id)
        if self.job_id is not None:
            self._tokens["job_id"] = job_id_var.set(self.job_id)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context and restore variables."""
        for key, token in self._tokens.items():
            if key == "request_id":
                request_id_var.reset(token)
            elif key == "user_id":
                user_id_var.reset(token)
            elif key == "book_id":
                book_id_var.reset(token)
            elif key == "job_id":
                job_id_var.reset(token)


# Convenience function for creating log context
def log_context(
    *,
    request_id: str | None = None,
    user_id: str | None = None,
    book_id: str | None = None,
    job_id: str | None = None,
) -> LogContext:
    """Create a log context manager."""
    return LogContext(
        request_id=request_id,
        user_id=user_id,
        book_id=book_id,
        job_id=job_id,
    )
