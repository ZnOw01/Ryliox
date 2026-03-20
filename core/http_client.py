import asyncio
import logging
import time
from collections.abc import Mapping, Sequence
from http.cookiejar import Cookie
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

import config
from core.session_store import SessionStore
from core.url_utils import normalize_remote_url

logger = logging.getLogger(__name__)


def _parse_cookie_expires(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    if isinstance(value, (int, float)):
        return int(float(value))
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(float(stripped))
        except ValueError:
            return None
    return None


class HttpClient:
    def __init__(self, cookies_file: Path | None = None):
        self.client = httpx.AsyncClient(headers=config.HEADERS)
        self.last_request_time = 0.0
        self._rate_limit_lock = asyncio.Lock()
        self._cookie_domain = self._resolve_cookie_domain(config.BASE_URL)
        self._request_retries = max(0, int(getattr(config.SETTINGS, "request_retries", 2)))
        self._request_retry_backoff = max(0.0, float(getattr(config.SETTINGS, "request_retry_backoff", 0.5)))

        cookies_path = cookies_file or config.COOKIES_FILE
        self.session_store = SessionStore(legacy_cookies_file=cookies_path)
        self._load_cookies_from_store()

    def _resolve_cookie_domain(self, base_url: str) -> str:
        try:
            return (urlparse(base_url).hostname or "").lower()
        except ValueError:
            return ""

    def _build_cookie(self, record: Mapping[str, Any]) -> Cookie:
        domain = str(record.get("domain") or self._cookie_domain or "").strip().lower()
        path = str(record.get("path") or "/").strip() or "/"
        secure = bool(record.get("secure"))
        expires = _parse_cookie_expires(record.get("expires"))
        rest: dict[str, Any] = {}
        if record.get("http_only"):
            rest["HttpOnly"] = True
        same_site = str(record.get("same_site") or "").strip()
        if same_site:
            rest["SameSite"] = same_site

        return Cookie(
            version=0,
            name=str(record["name"]),
            value=str(record["value"]),
            port=None,
            port_specified=False,
            domain=domain,
            domain_specified=bool(domain),
            domain_initial_dot=domain.startswith("."),
            path=path,
            path_specified=True,
            secure=secure,
            expires=expires,
            discard=expires is None,
            comment=None,
            comment_url=None,
            rest=rest,
            rfc2109=False,
        )

    def _apply_cookies(self, cookies: Sequence[Mapping[str, Any]]):
        for record in cookies:
            self.client.cookies.jar.set_cookie(self._build_cookie(record))

    def _load_cookies_from_store(self):
        try:
            cookies = self.session_store.load_cookie_records(migrate_legacy=True)
        except Exception:
            logger.exception("Failed to load cookies from SessionStore.")
            cookies = []
        self._apply_cookies(cookies)

    def _normalize_request_url(self, url: str) -> str:
        if not url.startswith(("http://", "https://")):
            url = urljoin(config.BASE_URL, url)
        normalized = normalize_remote_url(url, base_url=config.BASE_URL)
        if not normalized:
            raise ValueError(f"Blocked unsafe request URL: {url!r}")
        return normalized

    async def _request_with_safe_redirects(self, url: str, **kwargs) -> httpx.Response:
        max_redirects = 10
        current_url = url
        request_kwargs = dict(kwargs)
        request_kwargs["follow_redirects"] = False

        for _ in range(max_redirects + 1):
            await self._rate_limit()
            response = await self.client.get(current_url, **request_kwargs)
            if not response.is_redirect:
                return response

            location = response.headers.get("location")
            if not location:
                return response

            next_url = urljoin(str(response.request.url), location)
            normalized_next_url = normalize_remote_url(
                next_url, base_url=config.BASE_URL
            )
            if not normalized_next_url:
                raise ValueError(f"Blocked unsafe redirect URL: {next_url!r}")
            current_url = normalized_next_url

        raise RuntimeError("Too many redirects while fetching remote URL")

    async def _rate_limit(self):
        async with self._rate_limit_lock:
            elapsed = time.monotonic() - self.last_request_time
            if elapsed < config.REQUEST_DELAY:
                await asyncio.sleep(config.REQUEST_DELAY - elapsed)
            self.last_request_time = time.monotonic()

    async def get(self, url: str, **kwargs) -> httpx.Response:
        url = self._normalize_request_url(url)
        follow_redirects = bool(kwargs.pop("follow_redirects", False))
        if "allow_redirects" in kwargs:
            follow_redirects = bool(kwargs.pop("allow_redirects"))
        kwargs.setdefault("timeout", config.REQUEST_TIMEOUT)
        attempts = self._request_retries + 1
        for attempt in range(attempts):
            try:
                if follow_redirects:
                    response = await self._request_with_safe_redirects(url, **kwargs)
                else:
                    await self._rate_limit()
                    response = await self.client.get(
                        url, follow_redirects=False, **kwargs
                    )
            except httpx.RequestError:
                if attempt >= self._request_retries:
                    raise
                await asyncio.sleep(self._request_retry_backoff * (2 ** attempt))
                continue
            except ValueError:
                raise

            if response.status_code not in {429, 500, 502, 503, 504} or attempt >= self._request_retries:
                return response

            await asyncio.sleep(self._request_retry_backoff * (2 ** attempt))

        raise RuntimeError("Unexpected request retry flow termination")

    async def get_json(self, url: str, **kwargs) -> dict:
        response = await self.get(url, **kwargs)
        response.raise_for_status()
        return response.json()

    async def get_text(self, url: str, **kwargs) -> str:
        response = await self.get(url, **kwargs)
        response.raise_for_status()
        raw = response.content
        candidates: list[str] = ["utf-8"]
        if response.encoding:
            candidates.append(response.encoding)
        apparent_encoding = getattr(response, "apparent_encoding", None)
        if apparent_encoding:
            candidates.append(apparent_encoding)
        candidates.append("latin-1")

        seen = set()
        for encoding in candidates:
            key = str(encoding).lower()
            if key in seen:
                continue
            seen.add(key)
            try:
                return raw.decode(encoding)
            except (LookupError, UnicodeDecodeError):
                continue

        return raw.decode("utf-8", errors="replace")

    async def get_bytes(self, url: str, **kwargs) -> bytes:
        response = await self.get(url, **kwargs)
        response.raise_for_status()
        return response.content

    def reload_cookies(self):
        """Clear and reload cookies from session store after browser login."""
        self.client.cookies.clear()
        self._load_cookies_from_store()

    async def close(self):
        await self.client.aclose()
