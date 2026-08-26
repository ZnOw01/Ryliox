"""Structured logging configuration with JSON support."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import UTC, datetime
from typing import Any


class JSONLogFormatter(logging.Formatter):
    """JSON formatter for structured logging in production."""

    @staticmethod
    def _json_default(obj: Any) -> Any:
        """Handle non-serializable objects."""
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        if isinstance(obj, Exception):
            return f"{obj.__class__.__name__}: {obj!s}"
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        if isinstance(obj, str):
            return obj.replace("\x00", "\\x00").replace("\x01", "\\x01")
        return str(obj)

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

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

        log_data["source"] = {
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName,
        }

        return json.dumps(
            log_data,
            ensure_ascii=False,
            separators=(",", ":"),
            default=self._json_default,
            allow_nan=False,
        )


class ColoredConsoleFormatter(logging.Formatter):
    """Colored formatter for development environments."""

    COLORS: dict[str, str] = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET: str = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format with colors for terminal output."""
        color = self.COLORS.get(record.levelname, "")
        reset = self.RESET if color else ""

        return (
            f"{color}{record.levelname:8}{reset} | "
            f"{time.strftime('%H:%M:%S', time.localtime(record.created))} | "
            f"{record.name:20} | "
            f"{record.getMessage()}"
        )


def configure_logging(
    *,
    level: str | None = None,
    json_format: bool | None = None,
) -> None:
    """Configure structured logging for the application."""
    raw_level = level if level is not None else os.getenv("LOG_LEVEL") or "INFO"
    log_level = raw_level.upper()

    is_production = os.getenv("ENVIRONMENT", "development").lower() in (
        "production",
        "prod",
    )
    use_json = json_format if json_format is not None else is_production

    if use_json:
        formatter: logging.Formatter = JSONLogFormatter()
    else:
        formatter = ColoredConsoleFormatter()

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, log_level, logging.INFO))
    root_logger.addHandler(console_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured: level=%s, format=%s",
        log_level,
        "JSON" if use_json else "colored",
    )
