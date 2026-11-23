"""An httpx transport that sends requests through curl_cffi with a browser's fingerprint.

O'Reilly sits behind Akamai, which compares the client's TLS and HTTP/2 handshake with the
browser that earned the session's ``_abck`` cookie. httpx's own handshake is Python's, so
with a real session Akamai answers "Access Denied" even though the session is valid.
curl_cffi performs the handshake of a real browser build.

Only the wire changes. httpx still builds the request and handles cookies, redirects
(Ryliox validates each hop itself) and the response API the rest of the code uses.
"""

from __future__ import annotations

import httpx
from curl_cffi.requests import AsyncSession
from curl_cffi.requests import exceptions as curl_errors

# httpx adds these on its own. A browser profile supplies its own values, and sending
# httpx's would contradict the fingerprint (``python-httpx`` user agent) or the protocol
# (``Connection`` is forbidden in HTTP/2; curl sets ``Host`` and decodes the body itself).
_DROPPED_HEADERS = frozenset({"host", "connection", "accept-encoding", "content-length"})

# curl has already decoded the body, so these no longer describe it.
_STALE_RESPONSE_HEADERS = frozenset({"content-encoding", "content-length", "transfer-encoding"})


class BrowserTransport(httpx.AsyncBaseTransport):
    """Send httpx requests through curl_cffi, impersonating ``impersonate`` (e.g. ``"chrome"``)."""

    def __init__(self, impersonate: str) -> None:
        self._impersonate = impersonate
        self._session: AsyncSession | None = None

    def _get_session(self) -> AsyncSession:
        # Created on first use, inside the event loop that will drive it: the download
        # queue runs each job on its own loop.
        if self._session is None:
            self._session = AsyncSession(impersonate=self._impersonate)
        return self._session

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        headers = [
            (name, value)
            for name, value in request.headers.multi_items()
            if name.lower() not in _DROPPED_HEADERS
            and not (name.lower() == "user-agent" and value.startswith("python-httpx/"))
        ]
        timeout = request.extensions.get("timeout", {})
        connect, read = timeout.get("connect"), timeout.get("read")
        try:
            response = await self._get_session().request(
                request.method,  # type: ignore[arg-type]
                str(request.url),
                headers=headers,
                data=request.content or None,
                timeout=(connect or 30.0, read or 30.0),
                allow_redirects=False,
                # httpx owns the cookie jar; curl must neither add nor keep cookies.
                discard_cookies=True,
            )
        except curl_errors.Timeout as exc:
            raise httpx.TimeoutException(str(exc), request=request) from exc
        except (curl_errors.ConnectionError, curl_errors.DNSError) as exc:
            raise httpx.ConnectError(str(exc), request=request) from exc
        except curl_errors.RequestException as exc:
            raise httpx.TransportError(str(exc), request=request) from exc

        return httpx.Response(
            status_code=response.status_code,
            headers=[
                (name, value)
                for name, value in response.headers.multi_items()
                if name.lower() not in _STALE_RESPONSE_HEADERS and value is not None
            ],
            content=response.content,
            request=request,
        )

    async def aclose(self) -> None:
        if self._session is not None:
            session, self._session = self._session, None
            await session.close()
