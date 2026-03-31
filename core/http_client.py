import asyncio
import logging
import time
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlparse

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

logger = logging.getLogger(__name__)

DEFAULT_REQUEST_RETRIES = 2
DEFAULT_REQUEST_RETRY_BACKOFF = 0.5
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# Connection pooling limits
DEFAULT_MAX_KEEPALIVE_CONNECTIONS = 20
DEFAULT_MAX_CONNECTIONS = 100
DEFAULT_CONNECTION_TIMEOUT = 5.0
DEFAULT_POOL_TIMEOUT = 30.0


class HttpClientError(Exception):
    """Custom exception for HTTP client errors with context."""

    pass


class HttpClient:
    """HTTP client with connection pooling, rate limiting, and retry logic."""

    _shared_client: httpx.AsyncClient | None = None
    _shared_client_ref_count: int = 0
    _shared_client_lock: asyncio.Lock = asyncio.Lock()

    def __init__(self, cookies_file: Path | None = None):
        self._client: httpx.AsyncClient | None = None
        self._owns_client: bool = False
        self.last_request_time = 0.0
        self._rate_limit_lock = asyncio.Lock()
        self._cookie_domain = self._resolve_cookie_domain(config.BASE_URL)
        self._request_retries = max(
            0, int(getattr(config.SETTINGS, "request_retries", DEFAULT_REQUEST_RETRIES))
        )
        self._request_retry_backoff = max(
            0.0,
            float(
                getattr(
                    config.SETTINGS,
                    "request_retry_backoff",
                    DEFAULT_REQUEST_RETRY_BACKOFF,
                )
            ),
        )

        cookies_path = cookies_file or config.COOKIES_FILE
        self.session_store = SessionStore(legacy_cookies_file=cookies_path)

    @classmethod
    async def _get_or_create_shared_client(cls) -> httpx.AsyncClient:
        """Get or create a shared AsyncClient with connection pooling."""
        async with cls._shared_client_lock:
            if cls._shared_client is None:
                limits = httpx.Limits(
                    max_keepalive_connections=DEFAULT_MAX_KEEPALIVE_CONNECTIONS,
                    max_connections=DEFAULT_MAX_CONNECTIONS,
                    keepalive_expiry=30.0,
                )
                timeout = httpx.Timeout(
                    connect=DEFAULT_CONNECTION_TIMEOUT,
                    pool=DEFAULT_POOL_TIMEOUT,
                    read=config.REQUEST_TIMEOUT,
                    write=config.REQUEST_TIMEOUT,
                )
                cls._shared_client = httpx.AsyncClient(
                    headers=config.HEADERS,
                    limits=limits,
                    timeout=timeout,
                    http2=False,  # HTTP/2 can cause issues with some servers
                )
                logger.debug(
                    "Created shared HTTP client with pool limits: keepalive=%d, max=%d",
                    DEFAULT_MAX_KEEPALIVE_CONNECTIONS,
                    DEFAULT_MAX_CONNECTIONS,
                )
            cls._shared_client_ref_count += 1
            return cls._shared_client

    @classmethod
    async def _release_shared_client(cls) -> None:
        """Release reference to shared client, closing if no more refs."""
        async with cls._shared_client_lock:
            cls._shared_client_ref_count -= 1
            if cls._shared_client_ref_count <= 0 and cls._shared_client is not None:
                await cls._shared_client.aclose()
                cls._shared_client = None
                cls._shared_client_ref_count = 0
                logger.debug("Closed shared HTTP client")

    @property
    def client(self) -> httpx.AsyncClient:
        """Get the HTTP client, initializing if needed."""
        if self._client is None:
            raise RuntimeError("HttpClient not initialized. Use async context manager.")
        return self._client

    async def __aenter__(self) -> "HttpClient":
        """Async context manager entry - initializes client."""
        self._client = await self._get_or_create_shared_client()
        self._owns_client = True
        self._load_cookies_from_store()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - releases client reference."""
        if self._owns_client:
            await self._release_shared_client()
            self._client = None
            self._owns_client = False

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
        """Fetch URL with rate limiting and automatic retries."""
        if not url.startswith("http"):
            url = config.BASE_URL + url
        if "allow_redirects" in kwargs:
            follow_redirects = bool(kwargs.pop("allow_redirects"))
        kwargs.setdefault("timeout", config.REQUEST_TIMEOUT)
        attempts = self._request_retries + 1
        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                response = await self.client.get(url, **kwargs)
            except httpx.RequestError as exc:
                last_error = exc
                logger.warning(
                    "HTTP request failed (attempt %d/%d): %s %s - %s",
                    attempt + 1,
                    attempts,
                    exc.__class__.__name__,
                    url,
                    str(exc),
                )
                if attempt >= self._request_retries:
                    raise HttpClientError(
                        f"Request failed after {attempts} attempts: {exc.__class__.__name__}: {exc}"
                    ) from exc
                await asyncio.sleep(self._request_retry_backoff * (2**attempt))
                continue
            except ValueError:
                raise

            if (
                response.status_code not in RETRYABLE_STATUS_CODES
                or attempt >= self._request_retries
            ):
                if response.status_code >= 400:
                    logger.warning(
                        "HTTP error response: %s %s - status=%d (attempt %d/%d)",
                        response.request.method if response.request else "GET",
                        url,
                        response.status_code,
                        attempt + 1,
                        attempts,
                    )
                return response

            logger.info(
                "Retrying request due to status %d: %s (attempt %d/%d)",
                response.status_code,
                url,
                attempt + 1,
                attempts,
            )
            await asyncio.sleep(self._request_retry_backoff * (2**attempt))

        raise HttpClientError(
            f"Unexpected request retry flow termination after {attempts} attempts. "
            f"Last error: {last_error.__class__.__name__ if last_error else 'None'}"
        )

    async def get_json(self, url: str, **kwargs) -> dict:
        """Fetch JSON response from URL."""
        response = await self.get(url, **kwargs)
        try:
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "JSON fetch failed: %s - status=%d - response=%s",
                url,
                exc.response.status_code if hasattr(exc, "response") else "unknown",
                exc.response.text[:200] if hasattr(exc, "response") else "no response",
            )
            raise HttpClientError(
                f"Failed to fetch JSON from {url}: HTTP {exc.response.status_code}"
            ) from exc
        except Exception as exc:
            logger.error("JSON parse error: %s - error=%s", url, str(exc))
            raise HttpClientError(
                f"Failed to parse JSON response from {url}: {exc.__class__.__name__}"
            ) from exc

    async def get_text(self, url: str, **kwargs) -> str:
        """Fetch text response from URL with encoding detection."""
        response = await self.get(url, **kwargs)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Text fetch failed: %s - status=%d",
                url,
                exc.response.status_code if hasattr(exc, "response") else "unknown",
            )
            raise HttpClientError(
                f"Failed to fetch text from {url}: HTTP {exc.response.status_code}"
            ) from exc

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
            except (LookupError, UnicodeDecodeError) as exc:
                logger.debug(
                    "Encoding decode failed for %s: %s - %s", url, encoding, str(exc)
                )
                continue

        logger.warning(
            "All encoding attempts failed for %s, using fallback with replacement", url
        )
        return raw.decode("utf-8", errors="replace")

    async def get_bytes(self, url: str, **kwargs) -> bytes:
        """Fetch raw bytes response from URL."""
        response = await self.get(url, **kwargs)
        try:
            response.raise_for_status()
            return response.content
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Bytes fetch failed: %s - status=%d - content_length=%s",
                url,
                exc.response.status_code if hasattr(exc, "response") else "unknown",
                len(exc.response.content) if hasattr(exc, "response") else "unknown",
            )
            raise HttpClientError(
                f"Failed to fetch bytes from {url}: HTTP {exc.response.status_code}"
            ) from exc

    def reload_cookies(self):
        """Clear and reload cookies from session store after browser login."""
        self.client.cookies.clear()
        self._load_cookies_from_store()

    async def close(self):
        """Close the HTTP client session.

        This is now handled by __aexit__, but kept for backwards compatibility.
        """
        if self._owns_client:
            await self._release_shared_client()
            self._client = None
            self._owns_client = False
