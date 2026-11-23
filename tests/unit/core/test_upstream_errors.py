from __future__ import annotations

import tempfile
from pathlib import Path

import httpx
import pytest

import config
from core.http_client import HttpClient, UpstreamAuthError, UpstreamBlockedError

pytestmark = pytest.mark.unit

AKAMAI_PAGE = (
    "<HTML><HEAD>\n<TITLE>Access Denied</TITLE>\n</HEAD><BODY>\n<H1>Access Denied</H1>\n"
    "You don't have permission to access this server.<P>\nReference&#32;&#35;18&#46;abc\n</BODY>\n</HTML>\n"
)


def _client_answering(response_for):
    """An HttpClient whose transport answers every request with ``response_for(request)``."""
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return response_for(request)

    # A cookies file of its own: config.COOKIES_FILE would make __aenter__ reload whatever
    # session another test left in the shared store, over the cookies set below.
    client = HttpClient(cookies_file=Path(tempfile.mkdtemp()) / "cookies.json")
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client._owns_client = True
    client._auth_cookies = {"orm-jwt": "x"}
    return client, calls


@pytest.mark.asyncio
async def test_anti_bot_block_is_reported_as_a_block_not_an_expired_session():
    client, calls = _client_answering(
        lambda _r: httpx.Response(403, headers={"content-type": "text/html"}, text=AKAMAI_PAGE)
    )
    async with client:
        with pytest.raises(UpstreamBlockedError) as excinfo:
            await client.get_json(f"{config.API_V2}/search/?query=python")

    assert excinfo.value.code == "upstream_blocked"
    assert "expired" not in str(excinfo.value).lower()
    # A block is not fixed by asking again at once; one request, no retry burst.
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_api_403_with_a_session_still_means_the_session_was_rejected():
    client, _ = _client_answering(
        lambda _r: httpx.Response(
            403, json={"detail": "Authentication credentials were not provided."}
        )
    )
    async with client:
        with pytest.raises(UpstreamAuthError) as excinfo:
            await client.get_json(f"{config.API_V2}/search/?query=python")

    assert excinfo.value.code == "session_rejected"


@pytest.mark.asyncio
async def test_403_without_cookies_asks_for_cookies():
    client, _ = _client_answering(lambda _r: httpx.Response(403, json={}))
    async with client:
        client._auth_cookies = {}
        with pytest.raises(UpstreamAuthError) as excinfo:
            await client.get_json(f"{config.API_V2}/search/?query=python")

    assert excinfo.value.code == "auth_required"


def test_upstream_errors_stay_runtime_errors_for_existing_callers():
    assert issubclass(UpstreamBlockedError, RuntimeError)
    assert issubclass(UpstreamAuthError, RuntimeError)


def test_a_failed_job_records_the_upstream_error_code(tmp_path):
    """The job record carries the code, so the UI can explain a block instead of raw text."""
    import threading
    from pathlib import Path
    from unittest.mock import MagicMock

    from core.dto import DownloadJobDTO
    from core.services import DownloadQueueService

    repository = MagicMock()
    repository.get.return_value = None
    repository.is_cancel_requested.return_value = False

    async def kernel_factory():
        return MagicMock()

    service = DownloadQueueService(
        kernel_factory=kernel_factory, repository=repository, error_log_dir=tmp_path
    )
    service._is_terminal_job = lambda _job_id: False  # type: ignore[method-assign]
    job = DownloadJobDTO(book_id="9781098156664", output_dir=Path(tmp_path), formats=["epub"])

    for exc, expected in [
        (UpstreamBlockedError("blocked"), "upstream_blocked"),
        (UpstreamAuthError("rejected", code="session_rejected"), "session_rejected"),
        (ValueError("something else"), "download_failed"),
    ]:
        repository.mark_failed.reset_mock()
        service._handle_job_exception(job, exc, threading.Event())
        error_dto = repository.mark_failed.call_args.args[1]
        assert error_dto.code == expected, (type(exc).__name__, error_dto.code)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cookies",
    [
        {},
        # Only Akamai's cookies: what a partial copy from the browser leaves.
        {"_abck": "sensor", "bm_sz": "size", "akaalb_LearningALB": "lb"},
        # Cookie names that are not O'Reilly's session at all.
        {"session_id": "x", "auth_token": "y"},
    ],
)
async def test_access_denied_without_a_session_cookie_asks_for_cookies(cookies):
    """Akamai denies a browser fingerprint with no O'Reilly session. That is not a block
    to wait out: the user has to save the session cookies."""
    client, _ = _client_answering(
        lambda _r: httpx.Response(403, headers={"content-type": "text/html"}, text=AKAMAI_PAGE)
    )
    async with client:
        client._auth_cookies = dict(cookies)
        with pytest.raises(UpstreamAuthError) as excinfo:
            await client.get_json(f"{config.API_V2}/search/?query=python")

    assert excinfo.value.code == "auth_required"
