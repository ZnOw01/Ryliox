from __future__ import annotations

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


def test_require_same_origin_ignores_forwarded_headers_by_default():
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

    with pytest.raises(ForbiddenOriginError):
        guard(request)
