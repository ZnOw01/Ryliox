"""Async HTTP client with URL allowlisting, redirect safety, and retry support.

The client is an :term:`async context manager`. Use it as::

    async with HttpClient(cookies_file=path) as client:
        response = await client.get(url)
        data = await client.get_json(url)

The underlying transport is :mod:`httpx`.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import threading
import time
from collections.abc import Iterable
from http.cookiejar import Cookie
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin, urlparse

import httpx

import config

if TYPE_CHECKING:
    from core.session_store import SessionStore

logger = logging.getLogger(__name__)


# Core O'Reilly hosts that are always allowed, regardless of configuration.
_CORE_ALLOWED_HOSTS: tuple[str, ...] = (
    "oreilly.com",
    "oreillystatic.com",
    "oreil.ly",
)


def _build_default_allowlist() -> tuple[str, ...]:
    """Union the core O'Reilly hosts with the hosts implied by ``config.BASE_URL``."""
    base = urlparse(config.BASE_URL).hostname or "oreilly.com"
    hosts: set[str] = set(_CORE_ALLOWED_HOSTS)
    hosts.add(base)
    hosts.add("www." + base if not base.startswith("www.") else base)
    hosts.add("cdn." + base if not base.startswith("cdn.") else base)
    return tuple(sorted(hosts))


# Hosts (and their subdomains) that the client is allowed to talk to.
# Anything else raises ``ValueError("Blocked unsafe request URL: ...")``.
DEFAULT_ALLOWED_HOSTS: tuple[str, ...] = _build_default_allowlist()


def _host_matches_any(host: str, allowed_hosts: Iterable[str]) -> bool:
    """Suffix-match ``host`` against ``allowed_hosts`` (exact or subdomain)."""
    return any(host == h or host.endswith("." + h) for h in allowed_hosts)


def host_is_allowed(host: str) -> bool:
    """Return True when ``host`` is an allowed host or one of its subdomains."""
    return _host_matches_any((host or "").lower(), DEFAULT_ALLOWED_HOSTS)


class UpstreamAuthError(RuntimeError):
    """O'Reilly refused the request because of the session: none, or one it rejected."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


class UpstreamBlockedError(RuntimeError):
    """O'Reilly's anti-bot layer refused the request. The session itself may be fine."""

    code = "upstream_blocked"


def _is_anti_bot_block(response: httpx.Response) -> bool:
    """Akamai answers a blocked request with an HTML "Access Denied" page.

    O'Reilly's API answers its own 403s with JSON, so an HTML body is the signal.
    """
    content_type = response.headers.get("content-type", "")
    return "text/html" in content_type and "access denied" in response.text[:2000].lower()


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
        self._allowed_hosts = allowed_hosts or DEFAULT_ALLOWED_HOSTS
        self._auth_cookies: dict[str, str] = {}
        self._auth_cookie_records: list[dict[str, Any]] = []
        self._client: httpx.AsyncClient | None = None
        self._owns_client: bool = False
        self._session_store: SessionStore | None = None
        self._rate_lock = threading.Lock()
        self.last_request_time: float = 0.0

    @staticmethod
    def _resolve_url(url: str) -> str:
        """Resolve a (possibly relative) URL against ``config.BASE_URL``."""
        parsed = urlparse(url)
        if parsed.scheme in ("http", "https"):
            return url
        base = config.BASE_URL.rstrip("/") + "/"
        return urljoin(base, url.lstrip("/"))

    # ---- lifecycle -------------------------------------------------------

    async def __aenter__(self) -> HttpClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=dict(config.HEADERS),
                timeout=config.SETTINGS.http.timeout,
            )
            self._owns_client = True
        self._load_cookies(self._cookies_file)
        self._apply_auth_cookies()
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

    def _get_session_store(self) -> SessionStore:
        """Return a lazily-created, instance-cached :class:`SessionStore`.

        Each construction opens the SQLite database, creates tables/indexes,
        scans for unencrypted rows, and chmods the file — so the instance is
        built once per client instead of once per persisted response.
        """
        if self._session_store is None:
            from core.session_store import SessionStore

            self._session_store = SessionStore(
                db_path=config.SESSION_DB_FILE,
                legacy_cookies_file=config.COOKIES_FILE,
            )
        return self._session_store

    def _load_cookies(self, path: Path) -> None:
        if Path(path) == Path(config.COOKIES_FILE):
            try:
                records = self._get_session_store().load_cookie_records(migrate_legacy=True)
                if records:
                    self._auth_cookie_records = [
                        dict(record)
                        for record in records
                        if not self._is_akamai_cookie(str(record["name"]))
                    ]
                    self._auth_cookies = {
                        str(record["name"]): str(record["value"])
                        for record in records
                        if not self._is_akamai_cookie(str(record["name"]))
                    }
                    return
            except Exception as exc:
                logger.debug("Could not load cookies from SessionStore: %s", exc)

        if not path or not path.exists():
            return
        try:
            raw = path.read_text(encoding="utf-8")
            cookies = json.loads(raw)
        except (OSError, json.JSONDecodeError, ValueError):
            return
        if isinstance(cookies, dict):
            self._auth_cookies = {k: v for k, v in cookies.items() if not self._is_akamai_cookie(k)}
            self._auth_cookie_records = [
                {"name": name, "value": value, "domain": None, "path": "/"}
                for name, value in self._auth_cookies.items()
            ]
        elif isinstance(cookies, list):
            converted: dict[str, str] = {}
            cookie_records: list[dict[str, Any]] = []
            for entry in cookies:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name")
                value = entry.get("value")
                if name and not self._is_akamai_cookie(str(name)):
                    converted[str(name)] = str(value or "")
                    cookie_records.append(dict(entry))
            self._auth_cookies = converted
            self._auth_cookie_records = cookie_records

    def _is_akamai_cookie(self, name: str) -> bool:
        return name.startswith(self._AKAMAI_COOKIE_PREFIXES)

    def reload_cookies(self) -> None:
        """Clear cookies and reload from disk. Sync for use from the route layer."""
        self._auth_cookies = {}
        self._auth_cookie_records = []
        self._load_cookies(self._cookies_file)

    def _apply_auth_cookies(self) -> None:
        if self._client is None:
            return
        jar = self._client.cookies
        jar.clear()
        if self._auth_cookie_records:
            for record in self._auth_cookie_records:
                cookie_args = {"path": str(record.get("path") or "/")}
                if record.get("domain"):
                    cookie_args["domain"] = str(record["domain"])
                jar.set(str(record["name"]), str(record["value"]), **cookie_args)
            return
        for name, value in self._auth_cookies.items():
            jar.set(name, value)

    def _should_persist_captured_cookies(self) -> bool:
        return Path(self._cookies_file) == Path(config.COOKIES_FILE)

    def _cookie_to_record(self, cookie: Cookie) -> dict[str, Any]:
        rest = getattr(cookie, "_rest", {}) or {}
        return {
            "name": cookie.name,
            "value": cookie.value or "",
            "domain": cookie.domain or None,
            "path": cookie.path or "/",
            "secure": bool(cookie.secure),
            "http_only": "HttpOnly" in rest or "httponly" in {str(k).lower() for k in rest},
            "expires": cookie.expires,
            "same_site": rest.get("SameSite") or rest.get("samesite"),
        }

    @staticmethod
    def _persist_would_change(
        captured: list[dict[str, Any]],
        expired_names: set[str],
        merged: dict[tuple[str, str, str], dict[str, Any]],
    ) -> bool:
        """Whether merging ``captured`` into ``merged`` would alter any record.

        Mirrors the merge applied by :meth:`_capture_response_cookies` so an
        all-no-op capture can skip rewriting the store entirely. Deliberately
        conservative: any uncertainty returns True (i.e. persist as before).
        """
        seen_names: set[str] = set()
        for record in captured:
            name = str(record["name"])
            domain = str(record.get("domain") or "")
            path = str(record.get("path") or "/")
            key = (name, domain, path)
            # Multiple captures for one name interact; take the safe path.
            if name in seen_names:
                return True
            seen_names.add(name)
            # A domain-less record replaces every scope of the same name; a
            # domain-scoped one also evicts the wildcard-domain entry.
            if not domain:
                if any(existing_key[0] == name and existing_key != key for existing_key in merged):
                    return True
            elif (name, "", path) in merged:
                return True
            if name in expired_names:
                if key in merged:
                    return True  # the stale entry would be dropped
                continue
            existing = merged.get(key)
            if existing is None:
                return True
            if (
                str(existing.get("value")) != str(record.get("value"))
                or str(existing.get("domain") or "") != domain
                or str(existing.get("path") or "/") != path
                or bool(existing.get("secure")) != bool(record.get("secure"))
                or bool(existing.get("http_only")) != bool(record.get("http_only"))
                or existing.get("expires") != record.get("expires")
                or (existing.get("same_site") or None) != (record.get("same_site") or None)
            ):
                return True
        return False

    def _capture_response_cookies(self, response: httpx.Response) -> None:
        """Persist cookies refreshed by the upstream service via Set-Cookie."""
        captured = [
            self._cookie_to_record(cookie)
            for cookie in response.cookies.jar
            if cookie.name and not self._is_akamai_cookie(cookie.name)
        ]
        if not captured:
            return

        now = time.time()
        expired_names = {
            str(record["name"])
            for record in captured
            if record.get("expires") is not None and int(record["expires"]) <= now
        }
        for name in expired_names:
            self._auth_cookies.pop(name, None)

        refreshed = [
            record
            for record in captured
            if record["name"] not in expired_names and record.get("value") is not None
        ]
        if refreshed:
            self._auth_cookies.update(
                {str(record["name"]): str(record["value"]) for record in refreshed}
            )
        if not self._should_persist_captured_cookies():
            return

        try:
            store = self._get_session_store()
            merged = {
                (
                    str(record["name"]),
                    str(record.get("domain") or ""),
                    str(record.get("path") or "/"),
                ): record
                for record in store.get_cookie_records()
            }
            if not self._persist_would_change(captured, expired_names, merged):
                return
            for record in captured:
                key = (
                    str(record["name"]),
                    str(record.get("domain") or ""),
                    str(record.get("path") or "/"),
                )
                if not record.get("domain"):
                    merged = {
                        existing_key: existing
                        for existing_key, existing in merged.items()
                        if existing_key[0] != str(record["name"])
                    }
                else:
                    merged.pop((str(record["name"]), "", key[2]), None)
                if record["name"] in expired_names:
                    merged.pop(key, None)
                else:
                    merged[key] = record
            store.save_cookies(list(merged.values()))
        except Exception as exc:
            logger.warning("Failed to persist refreshed cookies: %s", exc)

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
        # The shared allowlist plus any instance-specific hosts (custom
        # ``allowed_hosts`` overrides); both use the same suffix match.
        return host_is_allowed(host) or _host_matches_any(host, self._allowed_hosts)

    def _validate_request_url(self, url: str) -> None:
        if not self._is_host_allowed(url):
            raise ValueError(f"Blocked unsafe request URL: {url}")

    # ---- public request API ---------------------------------------------

    async def _rate_limit_async(self) -> None:
        # Reserve the next slot atomically so concurrent callers cannot all
        # observe the same stale timestamp and fire simultaneously; only the
        # (non-awaiting) read-modify-write happens under the lock.
        with self._rate_lock:
            elapsed = time.time() - self.last_request_time
            delay = config.SETTINGS.http.delay - elapsed
            self.last_request_time = time.time() + max(delay, 0.0)
        if delay > 0:
            await asyncio.sleep(delay)

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Issue a GET request with retry, URL safety, and manual redirect handling.

        ``allow_redirects=True`` switches off the underlying auto-follow so we
        can validate each redirect target before following it. Redirects that
        target disallowed hosts raise ``ValueError``.

        Relative URLs are resolved against ``config.BASE_URL``.
        """
        url = self._resolve_url(url)
        await self._rate_limit_async()
        self._validate_request_url(url)
        self._apply_auth_cookies()

        allow_redirects = kwargs.pop("allow_redirects", False)
        max_retries = config.SETTINGS.http.retries
        backoff = config.SETTINGS.http.retry_backoff

        attempt = 0
        while True:
            try:
                if not allow_redirects:
                    response = await self.client.get(url, **kwargs)
                    self._enforce_response_limit(response)
                    self._capture_response_cookies(response)
                    return response
                return await self._get_with_safe_redirects(url, kwargs)
            except httpx.RequestError:
                if attempt >= max_retries:
                    raise
                attempt += 1
                await asyncio.sleep(backoff * attempt)

    async def _get_with_safe_redirects(self, url: str, kwargs: dict[str, Any]) -> httpx.Response:
        current = url
        seen: set[str] = set()
        redirect_count = 0
        max_redirects = max(0, int(config.SETTINGS.http.max_redirects))
        while True:
            if current in seen:
                raise ValueError(f"Redirect loop detected for URL: {current}")
            seen.add(current)
            if not self._is_host_allowed(current):
                if current == url:
                    self._validate_request_url(current)
                raise ValueError(f"Blocked unsafe redirect URL: {current}")
            self._apply_auth_cookies()
            response = await self.client.get(current, follow_redirects=False, **kwargs)
            self._enforce_response_limit(response)
            self._capture_response_cookies(response)
            if response.status_code not in (301, 302, 303, 307, 308):
                return response
            location = response.headers.get("location")
            if not location:
                return response
            redirect_count += 1
            if redirect_count > max_redirects:
                raise ValueError(f"Redirect limit exceeded ({max_redirects})")
            if not location.startswith("http"):
                location = urljoin(current, location)
            current = location

    @staticmethod
    def _enforce_response_limit(response: httpx.Response) -> None:
        max_bytes = max(1, int(config.SETTINGS.http.max_response_size_mb)) * 1024 * 1024
        declared = response.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > max_bytes:
            raise ValueError("Upstream response exceeds configured size limit")
        if len(response.content) > max_bytes:
            raise ValueError("Upstream response exceeds configured size limit")

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
            if _is_anti_bot_block(response):
                raise UpstreamBlockedError(
                    "O'Reilly is temporarily blocking requests from this app. "
                    "Wait a few minutes before trying again; your session is not the problem."
                )
            if not self._auth_cookies:
                raise UpstreamAuthError(
                    "Not authenticated. Please copy cookies from your browser and POST them to /api/cookies.",
                    code="auth_required",
                )
            raise UpstreamAuthError(
                "O'Reilly rejected the session. Copy fresh cookies from your browser and save them again.",
                code="session_rejected",
            )
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code} fetching {response.url}")
