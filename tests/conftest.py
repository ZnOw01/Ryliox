"""Global pytest fixtures and configuration for Ryliox tests.

This module provides shared fixtures for all test types:
- Unit tests
- Integration tests
- E2E tests
- Performance tests
- Security tests
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import tempfile
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Add project root to path for imports
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
repo_root_str = str(REPO_ROOT)
if repo_root_str not in sys.path:
    sys.path.insert(0, repo_root_str)

from core.kernel import Kernel, create_default_kernel
from core.session_store import SessionStore
from core.download_queue import DownloadQueueService, DownloadJobStore
from web.server import create_app
from web.dependencies import (
    get_kernel,
    get_session_store,
    get_download_queue,
)


# ============================================================================
# Pytest Configuration
# ============================================================================


def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "e2e: mark test as an end-to-end test")
    config.addinivalue_line("markers", "performance: mark test as a performance test")
    config.addinivalue_line("markers", "security: mark test as a security test")
    config.addinivalue_line("markers", "slow: mark test as slow (skipped by default)")
    config.addinivalue_line(
        "markers", "rate_limit: mark test as related to rate limiting"
    )


def pytest_addoption(parser):
    """Add custom command-line options."""
    parser.addoption(
        "--run-slow", action="store_true", default=False, help="Run slow tests"
    )
    parser.addoption(
        "--run-e2e", action="store_true", default=False, help="Run E2E tests"
    )
    parser.addoption(
        "--run-performance",
        action="store_true",
        default=False,
        help="Run performance tests",
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on options."""
    skip_slow = pytest.mark.skip(reason="Need --run-slow option to run")
    skip_e2e = pytest.mark.skip(reason="Need --run-e2e option to run")
    skip_performance = pytest.mark.skip(reason="Need --run-performance option to run")

    if not config.getoption("--run-slow"):
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)

    if not config.getoption("--run-e2e"):
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip_e2e)

    if not config.getoption("--run-performance"):
        for item in items:
            if "performance" in item.keywords:
                item.add_marker(skip_performance)


# ============================================================================
# Path and Directory Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="function")
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture(scope="function")
def temp_db_path(temp_dir: Path) -> Path:
    """Return a temporary database file path."""
    return temp_dir / "test.db"


@pytest.fixture(scope="function")
def temp_output_dir(temp_dir: Path) -> Path:
    """Return a temporary output directory."""
    output_dir = temp_dir / "output"
    output_dir.mkdir(exist_ok=True)
    return output_dir


# ============================================================================
# Mock Data Fixtures
# ============================================================================


@pytest.fixture(scope="function")
def sample_cookies() -> dict[str, str]:
    """Return sample valid cookies for testing."""
    return {
        "session_id": "test_session_12345",
        "auth_token": "bearer_test_token_abc123",
        "user_id": "user_123",
    }


@pytest.fixture(scope="function")
def sample_book_data() -> dict[str, Any]:
    """Return sample book data for testing."""
    return {
        "id": "9780134685991",
        "ourn": "urn:orm:book:9780134685991",
        "title": "Effective Python",
        "authors": ["Brett Slatkin"],
        "publishers": ["Addison-Wesley Professional"],
        "description": "A comprehensive guide to writing better Python code.",
        "cover_url": "https://learning.oreilly.com/library/cover/9780134685991/",
        "isbn": "9780134685991",
        "language": "en",
        "publication_date": "2019-03-15",
        "virtual_pages": 320,
        "chapters_url": "https://learning.oreilly.com/api/v2/book/9780134685991/chapters/",
        "toc_url": "https://learning.oreilly.com/api/v2/book/9780134685991/toc/",
        "spine_url": "https://learning.oreilly.com/api/v2/book/9780134685991/spine/",
        "files_url": "https://learning.oreilly.com/api/v2/book/9780134685991/files/",
    }


@pytest.fixture(scope="function")
def sample_chapters_data() -> list[dict[str, Any]]:
    """Return sample chapter data for testing."""
    return [
        {
            "index": 0,
            "title": "Introduction",
            "virtual_pages": 10,
            "minutes_required": 15,
        },
        {
            "index": 1,
            "title": "Chapter 1: Pythonic Thinking",
            "virtual_pages": 25,
            "minutes_required": 30,
        },
        {
            "index": 2,
            "title": "Chapter 2: Functions",
            "virtual_pages": 30,
            "minutes_required": 45,
        },
        {
            "index": 3,
            "title": "Chapter 3: Classes and Inheritance",
            "virtual_pages": 35,
            "minutes_required": 50,
        },
        {"index": 4, "title": "Conclusion", "virtual_pages": 8, "minutes_required": 10},
    ]


@pytest.fixture(scope="function")
def sample_search_results() -> list[dict[str, Any]]:
    """Return sample search results for testing."""
    return [
        {
            "id": "9780134685991",
            "title": "Effective Python",
            "authors": ["Brett Slatkin"],
            "cover_url": "https://learning.oreilly.com/library/cover/9780134685991/",
        },
        {
            "id": "9781491946008",
            "title": "Fluent Python",
            "authors": ["Luciano Ramalho"],
            "cover_url": "https://learning.oreilly.com/library/cover/9781491946008/",
        },
    ]


# ============================================================================
# Kernel and Service Fixtures
# ============================================================================


@pytest.fixture(scope="function")
def mock_http_client() -> MagicMock:
    """Create a mock HTTP client."""
    mock = MagicMock()
    mock.get = AsyncMock(return_value=MagicMock(status_code=200, json=lambda: {}))
    mock.post = AsyncMock(return_value=MagicMock(status_code=200, json=lambda: {}))
    mock.close = AsyncMock()
    mock.reload_cookies = MagicMock()
    return mock


@pytest.fixture(scope="function")
def mock_kernel(
    mock_http_client: MagicMock, temp_dir: Path
) -> Generator[Kernel, None, None]:
    """Create a kernel with mocked plugins."""
    kernel = Kernel(http=mock_http_client)

    # Mock all plugins
    mock_auth = MagicMock()
    mock_auth.get_status = AsyncMock(return_value={"valid": True, "reason": None})

    mock_book = MagicMock()
    mock_book.search = AsyncMock(return_value=[])
    mock_book.fetch = AsyncMock(return_value={})

    mock_chapters = MagicMock()
    mock_chapters.fetch_list = AsyncMock(return_value=[])

    mock_downloader = MagicMock()
    mock_downloader.parse_formats = MagicMock(return_value=["epub"])
    mock_downloader.supports_chapter_selection = MagicMock(return_value=True)
    mock_downloader.download = AsyncMock(
        return_value=MagicMock(
            title="Test Book", files={"epub": str(temp_dir / "book.epub")}
        )
    )

    mock_output = MagicMock()
    mock_output.validate_dir = MagicMock(return_value=(True, None, temp_dir))
    mock_output.get_default_dir = MagicMock(return_value=temp_dir)

    kernel.register("auth", mock_auth)
    kernel.register("book", mock_book)
    kernel.register("chapters", mock_chapters)
    kernel.register("downloader", mock_downloader)
    kernel.register("output", mock_output)

    yield kernel


@pytest.fixture(scope="function")
def mock_session_store(temp_db_path: Path) -> SessionStore:
    """Create a session store with temporary database."""
    return SessionStore(
        db_path=temp_db_path, legacy_cookies_file=temp_db_path.parent / "cookies.json"
    )


@pytest.fixture(scope="function")
def mock_download_queue(temp_dir: Path, mock_kernel: Kernel) -> DownloadQueueService:
    """Create a download queue service with temporary database."""
    db_path = temp_dir / "downloads.db"
    error_log_dir = temp_dir / "logs"

    queue = DownloadQueueService(
        kernel_factory=lambda: mock_kernel,
        db_path=db_path,
        error_log_dir=error_log_dir,
        poll_interval_seconds=0.1,
    )
    return queue


# ============================================================================
# FastAPI App and TestClient Fixtures
# ============================================================================


@pytest.fixture(scope="function")
def test_app(
    mock_kernel: Kernel,
    mock_session_store: SessionStore,
    mock_download_queue: DownloadQueueService,
) -> Generator[FastAPI, None, None]:
    """Create a FastAPI test application with mocked dependencies."""
    app = create_app()

    # Override dependencies
    def override_get_kernel():
        return mock_kernel

    def override_get_session_store():
        return mock_session_store

    def override_get_download_queue():
        return mock_download_queue

    app.dependency_overrides[get_kernel] = override_get_kernel
    app.dependency_overrides[get_session_store] = override_get_session_store
    app.dependency_overrides[get_download_queue] = override_get_download_queue

    yield app

    # Cleanup
    mock_download_queue.stop()


@pytest.fixture(scope="function")
def test_client(test_app: FastAPI) -> Generator[TestClient, None, None]:
    """Create a TestClient for the test application."""
    with TestClient(test_app) as client:
        yield client


@pytest.fixture(scope="function")
def authenticated_client(
    test_client: TestClient,
    sample_cookies: dict[str, str],
    mock_kernel: Kernel,
) -> TestClient:
    """Create an authenticated test client with cookies set."""
    # Mock auth status to return valid
    mock_kernel._plugins["auth"].get_status = AsyncMock(
        return_value={"valid": True, "reason": None}
    )

    # Save cookies via API
    response = test_client.post(
        "/api/cookies", json=sample_cookies, headers={"Origin": "http://localhost:8000"}
    )
    assert response.status_code == 200

    return test_client


# ============================================================================
# Async Fixtures
# ============================================================================


@pytest_asyncio.fixture(scope="function")
async def async_test_client(test_app: FastAPI) -> AsyncGenerator[TestClient, None]:
    """Create an async TestClient for async endpoint testing."""
    async with TestClient(test_app) as client:
        yield client


@pytest_asyncio.fixture(scope="function")
async def running_download_queue(
    mock_download_queue: DownloadQueueService,
) -> AsyncGenerator[DownloadQueueService, None]:
    """Start and stop the download queue for testing."""
    mock_download_queue.start()
    try:
        yield mock_download_queue
    finally:
        mock_download_queue.stop()


# ============================================================================
# Playwright Fixtures (for E2E tests)
# ============================================================================


@pytest.fixture(scope="session")
def base_url() -> str:
    """Return the base URL for E2E tests."""
    return os.getenv("TEST_BASE_URL", "http://localhost:8000")


# ============================================================================
# Utility Fixtures
# ============================================================================


@pytest.fixture(scope="function")
def rate_limit_headers() -> dict[str, str]:
    """Return headers that trigger rate limiting for testing."""
    return {
        "X-Forwarded-For": "192.168.1.100",
        "Origin": "http://localhost:8000",
    }


@pytest.fixture(scope="function")
def malicious_payloads() -> dict[str, list[str]]:
    """Return various malicious payloads for security testing."""
    return {
        "path_traversal": [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        ],
        "xss": [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<iframe src='javascript:alert(1)'>",
        ],
        "sql_injection": [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "1' AND 1=1 --",
            "' UNION SELECT * FROM users --",
        ],
        "command_injection": [
            "; cat /etc/passwd",
            "| whoami",
            "`id`",
            "$(uname -a)",
        ],
    }
