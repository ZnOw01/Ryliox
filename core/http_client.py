import asyncio
import time
from pathlib import Path
from typing import Mapping

import httpx

import config
from core.session_store import SessionStore


class HttpClient:
    def __init__(self, cookies_file: Path | None = None):
        self.client = httpx.AsyncClient(headers=config.HEADERS)
        self.last_request_time = 0.0
        self._rate_limit_lock = asyncio.Lock()
        self._request_retries = max(0, int(getattr(config.SETTINGS, "request_retries", 2)))
        self._request_retry_backoff = max(0.0, float(getattr(config.SETTINGS, "request_retry_backoff", 0.5)))

        cookies_path = cookies_file or config.COOKIES_FILE
        self.session_store = SessionStore(legacy_cookies_file=cookies_path)
        self._load_cookies_from_store()

    def _apply_cookies(self, cookies: Mapping[str, str]):
        for name, value in cookies.items():
            self.client.cookies.set(str(name), str(value), domain=".oreilly.com")

    def _load_cookies_from_store(self):
        try:
            cookies = self.session_store.load_cookies(migrate_legacy=True)
        except Exception:
            cookies = {}
        self._apply_cookies(cookies)

    async def _rate_limit(self):
        async with self._rate_limit_lock:
            elapsed = time.monotonic() - self.last_request_time
            if elapsed < config.REQUEST_DELAY:
                await asyncio.sleep(config.REQUEST_DELAY - elapsed)
            self.last_request_time = time.monotonic()

    async def get(self, url: str, **kwargs) -> httpx.Response:
        if not url.startswith("http"):
            url = config.BASE_URL + url
        if "allow_redirects" in kwargs:
            kwargs["follow_redirects"] = kwargs.pop("allow_redirects")
        kwargs.setdefault("timeout", config.REQUEST_TIMEOUT)
        attempts = self._request_retries + 1
        for attempt in range(attempts):
            await self._rate_limit()
            try:
                response = await self.client.get(url, **kwargs)
            except httpx.RequestError:
                if attempt >= self._request_retries:
                    raise
                await asyncio.sleep(self._request_retry_backoff * (2 ** attempt))
                continue

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
