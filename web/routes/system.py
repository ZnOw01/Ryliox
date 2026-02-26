"""System, settings, and utility routes."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status

import config
from core.kernel import Kernel
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


def _uptime(request: Request) -> float:
    started_at = float(getattr(request.app.state, "started_at", time.monotonic()))
    return max(0.0, time.monotonic() - started_at)


def _app_version(request: Request) -> str:
    return str(getattr(request.app.state, "app_version", "dev"))


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    return HealthResponse(
        status="ok",
        uptime_seconds=_uptime(request),
        version=_app_version(request),
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

    config.OUTPUT_DIR = path
    return SetOutputDirResponse(path=str(path))
