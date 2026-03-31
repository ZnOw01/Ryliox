"""Prometheus metrics endpoint for monitoring."""

from __future__ import annotations

from fastapi import APIRouter, Response

from core.metrics import metrics

router = APIRouter(prefix="/metrics", tags=["monitoring"])


@router.get("")
async def metrics_endpoint() -> Response:
    """Prometheus metrics endpoint for scraping.

    Returns metrics in Prometheus exposition format.
    Requires prometheus-client to be installed and ENABLE_METRICS not set to false.

    Metrics include:
    - downloads_started_total: Counter for downloads started
    - downloads_completed_total: Counter for completed downloads
    - downloads_failed_total: Counter for failed downloads (by error type)
    - download_duration_seconds: Histogram of download durations
    - http_requests_total: Counter for HTTP requests
    - http_request_duration_seconds: Histogram of request latencies
    - errors_total: Counter for errors by type
    - rate_limit_hits_total: Counter for rate limiting hits
    - download_queue_size: Gauge for current queue size
    - active_downloads: Gauge for active download count
    - sqlite_connections_active: Gauge for SQLite connections
    - disk_usage_bytes: Gauge for disk usage
    - disk_free_bytes: Gauge for free disk space
    """
    content, content_type = metrics.generate_metrics()
    return Response(content=content, media_type=content_type)
