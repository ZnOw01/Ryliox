from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from starlette.requests import Request

import config
from web.dependencies import (
    DOWNLOAD_ERROR_LOG_DIR,
    DOWNLOAD_QUEUE_DB,
    ForbiddenOriginError,
    require_same_origin,
)

pytestmark = pytest.mark.unit


def test_launcher_paths_follow_config_data_dir():
    assert DOWNLOAD_QUEUE_DB == config.DATA_DIR / "download_jobs.sqlite3"
    assert DOWNLOAD_ERROR_LOG_DIR == config.DATA_DIR / "logs"


def test_config_runtime_values_are_lazy_until_accessed():
    reloaded = importlib.reload(config)

    assert getattr(reloaded, "_RUNTIME_VALUES", None) is None

    assert isinstance(reloaded.DATA_DIR, Path)
    assert getattr(reloaded, "_RUNTIME_VALUES", None) is not None


def test_config_output_dir_remains_reassignable(tmp_path):
    original_output_dir = config.OUTPUT_DIR

    try:
        config.OUTPUT_DIR = tmp_path
        assert config.OUTPUT_DIR == tmp_path
    finally:
        config.OUTPUT_DIR = original_output_dir


def _build_request(
    headers: dict[str, str],
    url: str = "http://localhost/api/cookies",
    method: str = "GET",
) -> Request:
    scheme, rest = url.split("://", 1)
    path = "/" + rest.split("/", 1)[1]
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [
            (k.lower().encode("latin-1"), v.encode("latin-1"))
            for k, v in headers.items()
        ],
        "scheme": scheme,
        "server": ("localhost", 80),
    }
    return Request(scope)


def test_require_same_origin_allows_safe_requests_without_origin_header():
    guard = require_same_origin("get_cookies")
    request = _build_request({"host": "localhost"})

    guard(request)


def test_require_same_origin_blocks_unsafe_requests_without_origin_header():
    guard = require_same_origin("save_cookies")
    request = _build_request({"host": "localhost"}, method="POST")

    with pytest.raises(ForbiddenOriginError):
        guard(request)


def test_require_same_origin_allows_matching_origin_header():
    guard = require_same_origin("get_cookies")
    request = _build_request(
        {
            "host": "localhost",
            "origin": "http://localhost",
        }
    )

    guard(request)


def test_require_same_origin_accepts_forwarded_headers_from_proxy():
    guard = require_same_origin("save_cookies")
    request = _build_request(
        {
            "host": "localhost",
            "origin": "https://app.example.com",
            "x-forwarded-host": "app.example.com",
            "x-forwarded-proto": "https",
        },
        method="POST",
    )

    guard(request)
