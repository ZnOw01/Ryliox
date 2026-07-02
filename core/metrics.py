"""Prometheus metrics collection for monitoring."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        Info,
        generate_latest,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


class MetricsManager:
    """Manages Prometheus metrics collection."""

    _instance: MetricsManager | None = None
    _initialized: bool = False

    def __new__(cls) -> MetricsManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._enabled = (
            PROMETHEUS_AVAILABLE and os.getenv("ENABLE_METRICS", "true").lower() != "false"
        )

        if not self._enabled:
            self._initialized = True
            return

        self._registry = CollectorRegistry()

        # Download metrics
        self.downloads_started: Counter = Counter(
            "downloads_started_total",
            "Total number of downloads started",
            ["format"],
            registry=self._registry,
        )

        self.downloads_completed: Counter = Counter(
            "downloads_completed_total",
            "Total number of downloads completed successfully",
            ["format"],
            registry=self._registry,
        )

        self.downloads_failed: Counter = Counter(
            "downloads_failed_total",
            "Total number of failed downloads",
            ["format", "error_type"],
            registry=self._registry,
        )

        self.downloads_cancelled: Counter = Counter(
            "downloads_cancelled_total",
            "Total number of cancelled downloads",
            registry=self._registry,
        )

        self.download_duration: Histogram = Histogram(
            "download_duration_seconds",
            "Download duration in seconds",
            ["format"],
            buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600],
            registry=self._registry,
        )

        # HTTP metrics
        self.http_requests_total: Counter = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status_code"],
            registry=self._registry,
        )

        self.http_request_duration: Histogram = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration",
            ["method", "endpoint"],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
            registry=self._registry,
        )

        # Error metrics
        self.errors_total: Counter = Counter(
            "errors_total",
            "Total errors by type",
            ["error_type", "component"],
            registry=self._registry,
        )

        # Rate limiting metrics
        self.rate_limit_hits: Counter = Counter(
            "rate_limit_hits_total",
            "Total rate limiting hits",
            ["endpoint"],
            registry=self._registry,
        )

        # Queue metrics
        self.queue_size: Gauge = Gauge(
            "download_queue_size",
            "Current number of jobs in the download queue",
            registry=self._registry,
        )

        self.active_downloads: Gauge = Gauge(
            "active_downloads",
            "Number of currently active downloads",
            registry=self._registry,
        )

        # System metrics
        self.sqlite_connections: Gauge = Gauge(
            "sqlite_connections_active",
            "Number of active SQLite connections",
            registry=self._registry,
        )

        self.disk_usage_bytes: Gauge = Gauge(
            "disk_usage_bytes",
            "Current disk usage in bytes",
            ["path"],
            registry=self._registry,
        )

        self.disk_free_bytes: Gauge = Gauge(
            "disk_free_bytes",
            "Available disk space in bytes",
            ["path"],
            registry=self._registry,
        )

        # Application info
        self.app_info: Info = Info(
            "app",
            "Application information",
            registry=self._registry,
        )

        app_version = os.getenv("APP_VERSION", "dev")
        self.app_info.info({"version": app_version, "name": "ryliox"})

        self._initialized = True

    @property
    def enabled(self) -> bool:
        """Check if metrics collection is enabled."""
        return self._enabled

    def record_download_started(self, fmt: str) -> None:
        """Record a download start."""
        if self._enabled:
            self.downloads_started.labels(format=fmt).inc()

    def record_download_completed(self, fmt: str, duration_seconds: float) -> None:
        """Record a successful download completion."""
        if self._enabled:
            self.downloads_completed.labels(format=fmt).inc()
            self.download_duration.labels(format=fmt).observe(duration_seconds)

    def record_download_failed(self, fmt: str, error_type: str) -> None:
        """Record a failed download."""
        if self._enabled:
            self.downloads_failed.labels(format=fmt, error_type=error_type).inc()

    def record_download_cancelled(self) -> None:
        """Record a cancelled download."""
        if self._enabled:
            self.downloads_cancelled.inc()

    def record_http_request(
        self, method: str, endpoint: str, status_code: int, duration_seconds: float
    ) -> None:
        """Record an HTTP request."""
        if self._enabled:
            self.http_requests_total.labels(
                method=method, endpoint=endpoint, status_code=str(status_code)
            ).inc()
            self.http_request_duration.labels(method=method, endpoint=endpoint).observe(
                duration_seconds
            )

    def record_error(self, error_type: str, component: str) -> None:
        """Record an error."""
        if self._enabled:
            self.errors_total.labels(error_type=error_type, component=component).inc()

    def record_rate_limit_hit(self, endpoint: str) -> None:
        """Record a rate limit hit."""
        if self._enabled:
            self.rate_limit_hits.labels(endpoint=endpoint).inc()

    def set_queue_size(self, size: int) -> None:
        """Set the current queue size."""
        if self._enabled:
            self.queue_size.set(size)

    def set_active_downloads(self, count: int) -> None:
        """Set the number of active downloads."""
        if self._enabled:
            self.active_downloads.set(count)

    def set_sqlite_connections(self, count: int) -> None:
        """Set the number of active SQLite connections."""
        if self._enabled:
            self.sqlite_connections.set(count)

    def update_disk_usage(self, path: str) -> None:
        """Update disk usage metrics for a path."""
        if not self._enabled:
            return

        try:
            import shutil

            usage = shutil.disk_usage(path)
            self.disk_usage_bytes.labels(path=path).set(usage.used)
            self.disk_free_bytes.labels(path=path).set(usage.free)
        except Exception as exc:
            logger.debug("Failed to update disk usage metrics for %s: %s", path, exc)

    def generate_metrics(self) -> tuple[bytes, str]:
        """Generate Prometheus metrics output."""
        if not self._enabled:
            return b"# Metrics disabled\n", "text/plain"

        return generate_latest(self._registry), CONTENT_TYPE_LATEST


# Global metrics manager instance
metrics = MetricsManager()


@contextmanager
def timed_download(fmt: str) -> Iterator[None]:
    """Context manager for timing downloads."""
    start_time = time.time()
    metrics.record_download_started(fmt)
    try:
        yield
        duration = time.time() - start_time
        metrics.record_download_completed(fmt, duration)
    except asyncio.CancelledError:
        metrics.record_download_cancelled()
        raise
    except Exception as e:
        duration = time.time() - start_time
        error_type = type(e).__name__
        metrics.record_download_failed(fmt, error_type)
        raise


class AsyncTimedDownload:
    """Async context manager for timing downloads."""

    def __init__(self, fmt: str):
        self.fmt = fmt
        self.start_time: float = 0

    async def __aenter__(self) -> AsyncTimedDownload:
        """Enter the async context."""
        self.start_time = time.time()
        metrics.record_download_started(self.fmt)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the async context."""
        if exc_type is None:
            duration = time.time() - self.start_time
            metrics.record_download_completed(self.fmt, duration)
        elif exc_type is asyncio.CancelledError:
            metrics.record_download_cancelled()
        else:
            error_type = exc_type.__name__ if exc_type else "Unknown"
            metrics.record_download_failed(self.fmt, error_type)


def async_timed_download(fmt: str) -> AsyncTimedDownload:
    """Create an async timed download context manager."""
    return AsyncTimedDownload(fmt)
