"""System, settings, and utility routes with advanced health checks."""

from __future__ import annotations

import logging
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

import config
from core.kernel import Kernel
from core.metrics import metrics
from core.feature_flags import feature_flags
from plugins.downloader import DownloaderPlugin
from web.api_utils import ErrorCode
from web.dependencies import get_kernel, require_same_origin
from web.schemas import (
    FormatsResponse,
    HealthResponse,
    OutputDirRequest,
    RevealRequest,
    RevealResponse,
    SetOutputDirResponse,
    SettingsResponse,
)

router = APIRouter(prefix="/api", tags=["system"])
_config_lock = threading.Lock()
logger = logging.getLogger(__name__)


def _uptime(request: Request) -> float:
    started_at = float(getattr(request.app.state, "started_at", time.monotonic()))
    return max(0.0, time.monotonic() - started_at)


def _app_version(request: Request) -> str:
    return str(getattr(request.app.state, "app_version", "dev"))


@router.get("/health", response_model=HealthResponse)
def health(
    request: Request,
    kernel: Kernel = Depends(get_kernel),
) -> HealthResponse:
    checks: dict[str, dict[str, Any]] = {}

    # Check 1: Auth plugin accessible
    try:
        auth_plugin = kernel.get("auth")
        checks["auth"] = {"ok": auth_plugin is not None, "error": None}
    except Exception as e:
        checks["auth"] = {"ok": False, "error": str(e)}
        logger.warning(f"Health check - auth plugin failed: {e}")

    # Check 2: Download queue database connectivity
    try:
        download_queue = getattr(request.app.state, "download_queue", None)
        if download_queue is not None:
            # Verify SQLite connectivity by checking repository's database
            repository = getattr(download_queue, "repository", None)
            if repository is not None:
                # Attempt a simple query through the repository
                latest = repository.get_latest()
                checks["download_queue"] = {"ok": True, "error": None}
            else:
                checks["download_queue"] = {
                    "ok": False,
                    "error": "Repository not available",
                }
        else:
            checks["download_queue"] = {"ok": False, "error": "Queue not initialized"}
    except Exception as e:
        checks["download_queue"] = {"ok": False, "error": str(e)}
        logger.warning(f"Health check - download_queue failed: {e}")

    # Check 3: Session store (SQLite) connectivity
    try:
        from core.session_store import SessionStore

        session_store = SessionStore()
        # Verify by attempting to get cookies count
        cookie_count = session_store._count_stored_cookies()
        checks["session_store"] = {
            "ok": True,
            "error": None,
            "cookie_count": cookie_count,
        }
    except Exception as e:
        checks["session_store"] = {"ok": False, "error": str(e)}
        logger.warning(f"Health check - session_store failed: {e}")

    # Determine overall status
    failed = [name for name, check in checks.items() if not check.get("ok")]
    if not failed:
        status = "ok"
    elif len(failed) < len(checks):
        status = "degraded"
    else:
        status = "error"

    # Log detailed status for debugging
    if status != "ok":
        failed_details = {name: checks[name].get("error") for name in failed}
        logger.warning(
            f"Health check status '{status}' - failed components: {failed_details}"
        )

    return HealthResponse(
        status=status,
        uptime_seconds=_uptime(request),
        version=_app_version(request),
    )


# Detailed health check schemas
class DiskHealthInfo(BaseModel):
    path: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    usage_percent: float
    healthy: bool


class MemoryHealthInfo(BaseModel):
    available: bool
    total_bytes: int | None = None
    available_bytes: int | None = None
    used_bytes: int | None = None
    percent: float | None = None


class ExternalAPIHealth(BaseModel):
    name: str
    url: str
    status: str  # "ok", "degraded", "error"
    response_time_ms: float
    error: str | None = None


class SQLiteConnectionsInfo(BaseModel):
    download_queue_connections: int
    session_store_connections: int
    healthy: bool


class DetailedHealthCheck(BaseModel):
    status: str
    uptime_seconds: float
    version: str
    timestamp: str
    checks: dict[str, Any]
    disk: DiskHealthInfo
    memory: MemoryHealthInfo
    external_apis: list[ExternalAPIHealth]
    sqlite: SQLiteConnectionsInfo
    metrics_enabled: bool


@router.get("/health/detailed", response_model=DetailedHealthCheck)
async def health_detailed(
    request: Request,
    kernel: Kernel = Depends(get_kernel),
) -> DetailedHealthCheck:
    """Advanced health check with detailed system metrics.

    Returns comprehensive health information including:
    - Component status (auth, download_queue, session_store)
    - Disk usage for output and data directories
    - Memory usage
    - External API response times
    - SQLite connection status
    - Metrics collection status
    """
    checks: dict[str, Any] = {}
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Check 1: Auth plugin
    try:
        auth_plugin = kernel.get("auth")
        checks["auth"] = {"status": "ok", "message": "Auth plugin accessible"}
    except Exception as e:
        checks["auth"] = {"status": "error", "message": str(e)}

    # Check 2: Download queue
    try:
        download_queue = getattr(request.app.state, "download_queue", None)
        if download_queue is not None:
            repository = getattr(download_queue, "repository", None)
            if repository is not None:
                latest = repository.get_latest()
                checks["download_queue"] = {
                    "status": "ok",
                    "message": "Database accessible",
                    "latest_job": latest.get("job_id") if latest else None,
                }
            else:
                checks["download_queue"] = {
                    "status": "error",
                    "message": "Repository not available",
                }
        else:
            checks["download_queue"] = {
                "status": "error",
                "message": "Queue not initialized",
            }
    except Exception as e:
        checks["download_queue"] = {"status": "error", "message": str(e)}

    # Check 3: Session store
    try:
        from core.session_store import SessionStore

        session_store = SessionStore()
        cookie_count = session_store._count_stored_cookies()
        checks["session_store"] = {
            "status": "ok",
            "message": "Session store accessible",
            "cookie_count": cookie_count,
        }
    except Exception as e:
        checks["session_store"] = {"status": "error", "message": str(e)}

    # Check 4: Disk usage
    disk_info = _check_disk_health()

    # Check 5: Memory usage
    memory_info = _check_memory_health()

    # Check 6: External APIs
    external_apis = await _check_external_apis()

    # Check 7: SQLite connections
    sqlite_info = _check_sqlite_connections(request)

    # Determine overall status
    failed_checks = [
        name for name, check in checks.items() if check.get("status") == "error"
    ]
    degraded_checks = [
        name for name, check in checks.items() if check.get("status") == "degraded"
    ]

    if failed_checks:
        overall_status = "error"
    elif degraded_checks:
        overall_status = "degraded"
    else:
        overall_status = "ok"

    # Check disk health for status downgrade
    if not disk_info.healthy and overall_status == "ok":
        overall_status = "degraded"

    return DetailedHealthCheck(
        status=overall_status,
        uptime_seconds=_uptime(request),
        version=_app_version(request),
        timestamp=timestamp,
        checks=checks,
        disk=disk_info,
        memory=memory_info,
        external_apis=external_apis,
        sqlite=sqlite_info,
        metrics_enabled=metrics.enabled,
    )


def _check_disk_health() -> DiskHealthInfo:
    """Check disk usage for output and data directories."""
    try:
        usage = shutil.disk_usage(config.OUTPUT_DIR)
        usage_percent = (usage.used / usage.total) * 100

        # Consider unhealthy if > 90% full
        healthy = usage_percent < 90

        return DiskHealthInfo(
            path=str(config.OUTPUT_DIR),
            total_bytes=usage.total,
            used_bytes=usage.used,
            free_bytes=usage.free,
            usage_percent=round(usage_percent, 2),
            healthy=healthy,
        )
    except Exception as e:
        return DiskHealthInfo(
            path=str(config.OUTPUT_DIR),
            total_bytes=0,
            used_bytes=0,
            free_bytes=0,
            usage_percent=0,
            healthy=False,
        )


def _check_memory_health() -> MemoryHealthInfo:
    """Check system memory usage."""
    try:
        import psutil

        mem = psutil.virtual_memory()
        return MemoryHealthInfo(
            available=True,
            total_bytes=mem.total,
            available_bytes=mem.available,
            used_bytes=mem.used,
            percent=mem.percent,
        )
    except ImportError:
        return MemoryHealthInfo(available=False)
    except Exception:
        return MemoryHealthInfo(available=False)


async def _check_external_apis() -> list[ExternalAPIHealth]:
    """Check response time of external APIs."""
    import httpx

    apis_to_check = [
        {"name": "base_site", "url": config.BASE_URL},
    ]

    results = []
    for api in apis_to_check:
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(api["url"])
                response_time = (time.time() - start) * 1000

                if response.status_code < 500:
                    status = "ok"
                    error = None
                else:
                    status = "degraded"
                    error = f"HTTP {response.status_code}"

                results.append(
                    ExternalAPIHealth(
                        name=api["name"],
                        url=api["url"],
                        status=status,
                        response_time_ms=round(response_time, 2),
                        error=error,
                    )
                )
        except Exception as e:
            response_time = (time.time() - start) * 1000
            results.append(
                ExternalAPIHealth(
                    name=api["name"],
                    url=api["url"],
                    status="error",
                    response_time_ms=round(response_time, 2),
                    error=str(e),
                )
            )

    return results


def _check_sqlite_connections(request: Request) -> SQLiteConnectionsInfo:
    """Check active SQLite connections."""
    download_queue_conn = 0
    session_store_conn = 0

    try:
        download_queue = getattr(request.app.state, "download_queue", None)
        if download_queue and hasattr(download_queue, "repository"):
            # Connection is active if repository exists and has _conn
            repository = download_queue.repository
            download_queue_conn = 1 if getattr(repository, "_conn", None) else 0
    except Exception:
        pass

    try:
        from core.session_store import SessionStore

        session_store = SessionStore()
        session_store_conn = 1 if getattr(session_store, "_conn", None) else 0
    except Exception:
        pass

    return SQLiteConnectionsInfo(
        download_queue_connections=download_queue_conn,
        session_store_connections=session_store_conn,
        healthy=download_queue_conn > 0 or session_store_conn > 0,
    )


@router.get("/settings", response_model=SettingsResponse)
def get_settings() -> SettingsResponse:
    return SettingsResponse(output_dir=str(config.OUTPUT_DIR))


@router.get("/formats", response_model=FormatsResponse)
def get_formats() -> FormatsResponse:
    return FormatsResponse(**DownloaderPlugin.get_formats_info())


@router.post(
    "/reveal",
    response_model=RevealResponse,
    dependencies=[Depends(require_same_origin("reveal_file"))],
)
async def reveal_file(
    data: RevealRequest = Body(default_factory=RevealRequest),
    kernel: Kernel = Depends(get_kernel),
) -> RevealResponse:
    if not data.path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "path required", "code": ErrorCode.PATH_REQUIRED},
        )

    path = Path(data.path).resolve()
    allowed_base = Path(config.OUTPUT_DIR).resolve()
    try:
        path.relative_to(allowed_base)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "Access denied", "code": ErrorCode.ACCESS_DENIED},
        )
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Path does not exist", "code": ErrorCode.PATH_NOT_FOUND},
        )

    system_plugin = kernel["system"]
    if not await system_plugin.reveal_in_file_manager(path):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to reveal file", "code": ErrorCode.REVEAL_FAILED},
        )

    return RevealResponse(success=True)


@router.post(
    "/settings/output-dir",
    response_model=SetOutputDirResponse,
    dependencies=[Depends(require_same_origin("set_output_dir"))],
)
async def set_output_dir(
    data: OutputDirRequest = Body(default_factory=OutputDirRequest),
    kernel: Kernel = Depends(get_kernel),
) -> SetOutputDirResponse:
    system_plugin = kernel["system"]
    output_plugin = kernel["output"]

    if data.browse:
        selected = await system_plugin.show_folder_picker(config.OUTPUT_DIR)
        if selected:
            with _config_lock:
                config.OUTPUT_DIR = Path(selected)
            return SetOutputDirResponse(path=str(selected))
        return SetOutputDirResponse(cancelled=True)

    if not data.path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "path required", "code": ErrorCode.PATH_REQUIRED},
        )

    success, message, path = output_plugin.validate_dir(data.path)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": message, "code": ErrorCode.INVALID_OUTPUT_DIR},
        )

    with _config_lock:
        config.OUTPUT_DIR = path
    return SetOutputDirResponse(path=str(path))


# ─────────────────────────────────────────────────────────────────────────────
# Feature Flags Endpoints
# ─────────────────────────────────────────────────────────────────────────────


class FeatureFlagsResponse(BaseModel):
    """Response model for feature flags."""

    flags: dict[str, bool]
    config: dict[str, dict[str, Any]]


class SingleFeatureFlagResponse(BaseModel):
    """Response model for single feature flag."""

    flag: str
    enabled: bool


@router.get("/feature-flags", response_model=FeatureFlagsResponse)
async def get_feature_flags_api():
    """Get all feature flags and their current states.

    Returns:
        Object containing all feature flags and their configurations.
    """
    return FeatureFlagsResponse(
        flags=feature_flags.get_all(), config=feature_flags.get_config()
    )


@router.get("/feature-flags/{flag_name}", response_model=SingleFeatureFlagResponse)
async def get_single_feature_flag(flag_name: str):
    """Get the state of a single feature flag.

    Args:
        flag_name: The name of the feature flag to check.

    Returns:
        Object with flag name and enabled state.
    """
    return SingleFeatureFlagResponse(
        flag=flag_name, enabled=feature_flags.is_enabled(flag_name)
    )
