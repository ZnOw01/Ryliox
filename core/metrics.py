"""Prometheus metrics collection for monitoring and observability.

This module provides Prometheus metrics for tracking:
- Download operations (started, completed, failed)
- HTTP request latencies
- Error rates by type
- Rate limiting hits
- System resource usage

Metrics are exposed via the /metrics endpoint for Prometheus scraping.
"""

from __future__ import annotations

import asyncio
import os
import time
from contextlib import contextmanager
from typing import Any, Final

# Try to import prometheus_client, but make it optional
try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        Info,
        CollectorRegistry,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )

    PROMETHEUS_AVAILABLE: Final[bool] = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


class MetricsManager:
    """Manages Prometheus metrics collection.

    Metrics are only collected if prometheus-client is installed and
    ENABLE_METRICS environment variable is not set to 'false'.
    """

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
            PROMETHEUS_AVAILABLE
            and os.getenv("ENABLE_METRICS", "true").lower() != "false"
        )

        if not self._enabled:
            self._initialized = True
            return

        # Create registry
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

        # Set app info
        app_version = os.getenv("APP_VERSION", "dev")
        self.app_info.info({"version": app_version, "name": "ryliox"})

        self._initialized = True

    @property
    def enabled(self) -> bool:
        """Check if metrics collection is enabled."""
        return self._enabled

    def record_download_started(self, format: str) -> None:
        """Record a download start."""
        if self._enabled:
            self.downloads_started.labels(format=format).inc()

    def record_download_completed(self, format: str, duration_seconds: float) -> None:
        """Record a successful download completion."""
        if self._enabled:
            self.downloads_completed.labels(format=format).inc()
            self.download_duration.labels(format=format).observe(duration_seconds)

    def record_download_failed(self, format: str, error_type: str) -> None:
        """Record a failed download."""
        if self._enabled:
            self.downloads_failed.labels(format=format, error_type=error_type).inc()

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
        except Exception:
            pass

    def generate_metrics(self) -> tuple[bytes, str]:
        """Generate Prometheus metrics output.

        Returns:
            Tuple of (metrics_bytes, content_type)
        """
        if not self._enabled:
            return b"# Metrics disabled\n", "text/plain"

        return generate_latest(self._registry), CONTENT_TYPE_LATEST


# Global metrics manager instance
metrics = MetricsManager()


@contextmanager
def timed_download(format: str):
    """Context manager for timing downloads and recording metrics.

    Usage:
        with timed_download("epub"):
            # perform download
            pass
    """
    start_time = time.time()
    metrics.record_download_started(format)
    try:
        yield
        duration = time.time() - start_time
        metrics.record_download_completed(format, duration)
    except asyncio.CancelledError:
        metrics.record_download_cancelled()
        raise
    except Exception as e:
        duration = time.time() - start_time
        error_type = type(e).__name__
        metrics.record_download_failed(format, error_type)
        raise


# Async context manager version for Python 3.11+ compatibility
import asyncio


class AsyncTimedDownload:
    """Async context manager for timing downloads."""

    def __init__(self, format: str):
        self.format = format
        self.start_time: float = 0

    async def __aenter__(self) -> "AsyncTimedDownload":
        self.start_time = time.time()
        metrics.record_download_started(self.format)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is None:
            duration = time.time() - self.start_time
            metrics.record_download_completed(self.format, duration)
        elif exc_type is asyncio.CancelledError:
            metrics.record_download_cancelled()
        else:
            error_type = exc_type.__name__ if exc_type else "Unknown"
            metrics.record_download_failed(self.format, error_type)


def async_timed_download(format: str) -> AsyncTimedDownload:
    """Create an async timed download context manager.

    Usage:
        async with async_timed_download("epub"):
            # perform async download
            pass
    """
    return AsyncTimedDownload(format)


# Decorator for timing functions
def timed(name: str, component: str = ""):
    """Decorator to time function execution and record metrics.

    Args:
        name: Name for the timing metric
        component: Component name for error tracking
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                # Could add custom timing metric here
                return result
            except Exception as e:
                metrics.record_error(type(e).__name__, component or name)
                raise

        return wrapper

    return decorator
