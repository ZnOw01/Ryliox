"""Shared fixtures for the Ryliox test suite."""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

# The suite must never touch a developer's real state or depend on their
# ``.env``: point every path at a throwaway directory and supply the keys that
# would otherwise be created in the user's configuration directory. This has to
# happen before ``config`` is first imported, which the project imports below do.
_STATE_DIR = Path(tempfile.mkdtemp(prefix="ryliox-tests-"))
atexit.register(shutil.rmtree, _STATE_DIR, ignore_errors=True)
os.environ.update(
    {
        "RYLIOX_ENV_FILE": str(_STATE_DIR / "no.env"),
        "RYLIOX_PATHS__DATA_DIR": str(_STATE_DIR / "data"),
        "RYLIOX_PATHS__OUTPUT_DIR": str(_STATE_DIR / "output"),
        "RYLIOX_PATHS__OUTPUT_ROOT": str(_STATE_DIR / "output"),
        "RYLIOX_AUDIT__LOG_FILE": str(_STATE_DIR / "data" / "audit.log"),
        "RYLIOX_AUDIT__HMAC_KEY": "0" * 64,
        "RYLIOX_SESSION__ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
    }
)

from core.kernel import Kernel
from core.repository import DownloadJobRepository
from core.services import DownloadQueueService
from core.session_store import SessionStore
from web.dependencies import (
    get_download_queue,
    get_kernel,
    get_session_store,
)
from web.server import create_app

if TYPE_CHECKING:
    from collections.abc import Generator

    from fastapi import FastAPI


@pytest.fixture
def clean_settings_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every variable the settings would read, for tests that build their own."""
    import config

    groups = set(config.Settings.model_fields)
    for name in list(os.environ):
        key = name.lower()
        if (
            name.upper() in config.SHORT_NAMES
            or key.startswith("ryliox_")
            or key.split("__")[0] in groups
        ):
            monkeypatch.delenv(name)


def pytest_addoption(parser):
    """Add custom command-line options."""
    parser.addoption("--run-slow", action="store_true", default=False, help="Run slow tests")
    parser.addoption("--run-e2e", action="store_true", default=False, help="Run E2E tests")
    parser.addoption(
        "--run-performance",
        action="store_true",
        default=False,
        help="Run performance tests",
    )
    parser.addoption(
        "--run-security", action="store_true", default=False, help="Run security tests"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on options."""
    skip_a11y = pytest.mark.skip(reason="Need --run-e2e option to run accessibility tests")
    skip_slow = pytest.mark.skip(reason="Need --run-slow option to run")
    skip_e2e = pytest.mark.skip(reason="Need --run-e2e option to run")
    skip_performance = pytest.mark.skip(reason="Need --run-performance option to run")
    skip_security = pytest.mark.skip(reason="Need --run-security option to run")

    if not config.getoption("--run-slow"):
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)

    if not config.getoption("--run-e2e"):
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip_e2e)
            if "a11y" in item.keywords or "tests/a11y/" in item.nodeid.replace("\\", "/"):
                item.add_marker(skip_a11y)

    if not config.getoption("--run-performance"):
        for item in items:
            if "performance" in item.keywords:
                item.add_marker(skip_performance)

    if not config.getoption("--run-security"):
        for item in items:
            if "security" in item.keywords or "tests/security/" in item.nodeid.replace("\\", "/"):
                item.add_marker(skip_security)


# ============================================================================
# Path and Directory Fixtures
# ============================================================================


@pytest.fixture(scope="function")
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture(scope="function")
def temp_db_path(temp_dir: Path) -> Path:
    """Return a temporary database file path."""
    return temp_dir / "test.db"


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
def mock_kernel(mock_http_client: MagicMock, temp_dir: Path) -> Generator[Kernel, None, None]:
    """Create a kernel with mocked plugins."""
    kernel = Kernel()
    # Manually inject the mock HTTP client to avoid needing async context manager
    kernel._http = mock_http_client

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
        return_value=MagicMock(title="Test Book", files={"epub": str(temp_dir / "book.epub")})
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
    """Create a session store with a temporary database.

    Pre-populated with a single test cookie so routes that gate on
    ``count_stored_cookies()`` (search, book info, chapters) succeed by
    default in integration tests. Tests that need an empty-cookies
    condition can override this fixture.
    """
    store = SessionStore(
        db_path=temp_db_path, legacy_cookies_file=temp_db_path.parent / "cookies.json"
    )
    store.save_cookies(
        {
            "name": "orm-rt",
            "value": "test-refresh-token",
            "domain": ".oreilly.com",
            "path": "/",
        }
    )
    return store


@pytest.fixture(scope="function")
def mock_download_queue(
    temp_dir: Path, mock_kernel: Kernel
) -> Generator[DownloadQueueService, None, None]:
    """Create a download queue service with temporary database."""
    db_path = temp_dir / "downloads.db"
    error_log_dir = temp_dir / "logs"

    repository = DownloadJobRepository(
        db_path=db_path,
        terminal_job_retention=50,
    )

    async def _kernel_factory() -> Kernel:
        return mock_kernel

    queue = DownloadQueueService(
        kernel_factory=_kernel_factory,
        repository=repository,
        error_log_dir=error_log_dir,
        poll_interval_seconds=0.1,
    )
    try:
        yield queue
    finally:
        queue.stop()


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
    with TestClient(test_app, raise_server_exceptions=False) as client:
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
        "/api/cookies", json=sample_cookies, headers={"Origin": "http://testserver"}
    )
    assert response.status_code == 200

    return test_client


# ============================================================================
# Playwright Fixtures (for E2E tests)
# ============================================================================


@pytest.fixture(scope="session")
def base_url() -> str:
    """Return the base URL for E2E tests."""
    url = os.getenv("TEST_BASE_URL", "http://localhost:8000").rstrip("/")
    try:
        with urlopen(f"{url}/api/health", timeout=1):  # nosec B310 - test availability probe
            pass
    except (OSError, URLError):
        pytest.skip(f"Live server is not available at {url}; set TEST_BASE_URL or start the API")
    return url
