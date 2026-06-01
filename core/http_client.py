"""Async HTTP client with URL allowlisting, redirect safety, and retry support.

The client is an :term:`async context manager`. Use it as::

    async with HttpClient(cookies_file=path) as client:
        response = await client.get(url)
        data = await client.get_json(url)

The underlying transport is :mod:`httpx`. For the (legacy) sync interface used
by the original O'Reilly-specific scraping path, see
:func:`get_sync_client`, which wraps the same client in ``asyncio.run``.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

import config

logger = logging.getLogger(__name__)


# Hosts (and their subdomains) that the client is allowed to talk to.
# Anything else raises ``ValueError("Blocked unsafe request URL: ...")``.
_DEFAULT_ALLOWED_HOSTS: tuple[str, ...] = (
    "oreilly.com",
    "oreillystatic.com",
    "oreil.ly",
)


class HttpClient:
    """Async HTTP client with built-in URL allowlist and retry."""

    _AKAMAI_COOKIE_PREFIXES = ("_abck", "bm_", "ak_", "akaalb_")

    def __init__(
        self,
        cookies_file: Path | None = None,
        *,
        allowed_hosts: tuple[str, ...] | None = None,
    ) -> None:
        self._cookies_file = cookies_file or config.COOKIES_FILE
        self._allowed_hosts = allowed_hosts or self._resolve_default_hosts()
        self._auth_cookies: dict[str, str] = {}
        self._client: httpx.AsyncClient | None = None
        self._owns_client: bool = False
        self.last_request_time: float = 0.0

    @staticmethod
    def _resolve_default_hosts() -> tuple[str, ...]:
        base = urlparse(config.BASE_URL).hostname or "oreilly.com"
        hosts: set[str] = set(_DEFAULT_ALLOWED_HOSTS)
        hosts.add(base)
        hosts.add("www." + base if not base.startswith("www.") else base)
        hosts.add("cdn." + base if not base.startswith("cdn.") else base)
        return tuple(hosts)

    # ---- lifecycle -------------------------------------------------------

    async def __aenter__(self) -> HttpClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=dict(config.HEADERS),
                timeout=config.REQUEST_TIMEOUT,
            )
            self._owns_client = True
        self._load_cookies(self._cookies_file)
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError(
                "HttpClient not initialized — use 'async with HttpClient(...) as client'"
            )
        return self._client

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            try:
                await self._client.aclose()
            finally:
                self._client = None
                self._owns_client = False

    # ---- cookies ---------------------------------------------------------

    def _load_cookies(self, path: Path) -> None:
        if not path or not path.exists():
            return
        try:
            raw = path.read_text(encoding="utf-8")
            cookies = json.loads(raw)
        except (OSError, json.JSONDecodeError, ValueError):
            return
        if isinstance(cookies, dict):
            self._auth_cookies = {k: v for k, v in cookies.items() if not self._is_akamai_cookie(k)}
        elif isinstance(cookies, list):
            converted: dict[str, str] = {}
            for entry in cookies:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name")
                value = entry.get("value")
                if name and not self._is_akamai_cookie(str(name)):
                    converted[str(name)] = str(value or "")
            self._auth_cookies = converted

    def _is_akamai_cookie(self, name: str) -> bool:
        return name.startswith(self._AKAMAI_COOKIE_PREFIXES)

    def reload_cookies(self) -> None:
        """Clear cookies and reload from disk. Sync for use from the route layer."""
        self._auth_cookies = {}
        self._load_cookies(self._cookies_file)

    def _apply_auth_cookies(self) -> None:
        if self._client is None:
            return
        jar = self._client.cookies
        jar.clear()
        for name, value in self._auth_cookies.items():
            jar.set(name, value)

    # ---- JWT helpers -----------------------------------------------------

    @staticmethod
    def _decode_jwt_payload(token: str) -> dict | None:
        try:
            payload_b64 = token.split(".")[1]
            padded = payload_b64 + "=" * (4 - len(payload_b64) % 4)
            return json.loads(base64.b64decode(padded))
        except Exception:
            return None

    def get_jwt_status(self) -> dict | None:
        token = self._auth_cookies.get("orm-jwt")
        if not token:
            return None
        payload = self._decode_jwt_payload(token)
        if not payload:
            return {"valid": False, "reason": "invalid_token"}
        exp = int(payload.get("exp", 0))
        expires_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(exp))
        if time.time() > exp - 60:
            return {"valid": False, "reason": "token_expired", "expires_at": expires_at}
        return {"valid": True, "reason": None, "expires_at": expires_at}

    def has_refresh_cookie(self) -> bool:
        return bool(self._auth_cookies.get("orm-rt"))

    # ---- URL safety ------------------------------------------------------

    def _is_host_allowed(self, url: str) -> bool:
        if not url or not url.startswith("http"):
            return True
        host = (urlparse(url).hostname or "").lower()
        if not host:
            return False
        if host in self._allowed_hosts:
            return True
        return any(host.endswith("." + h) for h in self._allowed_hosts)

    def _validate_request_url(self, url: str) -> None:
        if not self._is_host_allowed(url):
            raise ValueError(f"Blocked unsafe request URL: {url}")

    # ---- public request API ---------------------------------------------

    async def _rate_limit_async(self) -> None:
        elapsed = time.time() - self.last_request_time
        delay = config.REQUEST_DELAY - elapsed
        if delay > 0:
            await asyncio.sleep(delay)
        self.last_request_time = time.time()

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Issue a GET request with retry, URL safety, and manual redirect handling.

        ``allow_redirects=True`` switches off the underlying auto-follow so we
        can validate each redirect target before following it. Redirects that
        target disallowed hosts raise ``ValueError``.
        """
        await self._rate_limit_async()
        self._validate_request_url(url)
        self._apply_auth_cookies()

        allow_redirects = kwargs.pop("allow_redirects", False)
        max_retries = max(0, int(getattr(config, "REQUEST_RETRIES", 0)))
        backoff = float(getattr(config, "REQUEST_RETRY_BACKOFF", 0.5))

        attempt = 0
        while True:
            try:
                if not allow_redirects:
                    return await self.client.get(url, **kwargs)
                return await self._get_with_safe_redirects(url, kwargs)
            except httpx.RequestError:
                if attempt >= max_retries:
                    raise
                attempt += 1
                await asyncio.sleep(backoff * attempt)

    async def _get_with_safe_redirects(self, url: str, kwargs: dict[str, Any]) -> httpx.Response:
        current = url
        seen: set[str] = set()
        while True:
            if current in seen:
                raise ValueError(f"Redirect loop detected for URL: {current}")
            seen.add(current)
            if not self._is_host_allowed(current):
                if current == url:
                    self._validate_request_url(current)
                raise ValueError(f"Blocked unsafe redirect URL: {current}")
            response = await self.client.get(current, follow_redirects=False, **kwargs)
            if response.status_code not in (301, 302, 303, 307, 308):
                return response
            location = response.headers.get("location")
            if not location:
                return response
            if not location.startswith("http"):
                from urllib.parse import urljoin

                location = urljoin(current, location)
            current = location

    async def get_json(self, url: str, **kwargs: Any) -> dict:
        response = await self.get(url, **kwargs)
        self._raise_for_auth_error(response)
        response.raise_for_status()
        return response.json()

    async def get_text(self, url: str, **kwargs: Any) -> str:
        response = await self.get(url, **kwargs)
        self._raise_for_auth_error(response)
        response.raise_for_status()
        return response.text

    async def get_bytes(self, url: str, **kwargs: Any) -> bytes:
        response = await self.get(url, **kwargs)
        self._raise_for_auth_error(response)
        response.raise_for_status()
        return response.content

    def _raise_for_auth_error(self, response: httpx.Response) -> None:
        if response.status_code == 403:
            if not self._auth_cookies:
                raise RuntimeError(
                    "Not authenticated. Please copy cookies from your browser and POST them to /api/cookies."
                )
            raise RuntimeError(
                "Session token expired. Please copy fresh cookies from your browser and POST them to /api/cookies."
            )
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code} fetching {response.url}")


# ---------------------------------------------------------------------------
# Legacy sync shim — wraps the async client in ``asyncio.run`` for callers
# that have not been converted yet (kept narrow on purpose).
# ---------------------------------------------------------------------------


def _is_unsafe_redirect_target(text: str) -> bool:
    """Best-effort: scan a response body for absolute URLs to disallowed hosts."""
    pattern = re.compile(r"https?://([\w.\-]+)")
    for match in pattern.finditer(text):
        host = match.group(1).lower()
        if not any(host == h or host.endswith("." + h) for h in _DEFAULT_ALLOWED_HOSTS):
            return True
    return False
