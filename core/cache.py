"""In-memory LRU cache with TTL support."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Generic, TypeVar

import config

logger = logging.getLogger(__name__)

K = TypeVar("K")
V = TypeVar("V")


@dataclass
class CacheEntry(Generic[V]):
    """Cache entry with TTL support."""

    value: V
    created_at: float = field(default_factory=time.monotonic)
    expires_at: float | None = None

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.monotonic() > self.expires_at


class LRUCache(Generic[K, V]):
    """Async-safe LRU cache with TTL support."""

    def __init__(
        self,
        maxsize: int = 128,
        default_ttl: float | None = None,
        name: str = "default",
    ):
        if not isinstance(maxsize, int) or maxsize < 1:
            raise ValueError(f"maxsize must be a positive integer, got {maxsize!r}")
        self.maxsize = maxsize
        self.default_ttl = default_ttl
        self.name = name
        self._cache: OrderedDict[K, CacheEntry[V]] = OrderedDict()
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0
        self._cleanup_task: asyncio.Task | None = None
        self._cleanup_running = False

    async def get(self, key: K) -> V | None:
        """Get value from cache. Returns None if not found or expired."""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None

            self._cache.move_to_end(key)
            self._hits += 1
            return entry.value

    async def set(
        self, key: K, value: V, ttl: float | None = None, allow_update: bool = True
    ) -> None:
        """Set value in cache."""
        async with self._lock:
            if key in self._cache and not allow_update:
                return

            expires_at = None
            if ttl is not None:
                expires_at = time.monotonic() + ttl
            elif self.default_ttl is not None:
                expires_at = time.monotonic() + self.default_ttl

            entry = CacheEntry(value=value, expires_at=expires_at)

            if key in self._cache:
                del self._cache[key]

            self._cache[key] = entry

            while len(self._cache) > self.maxsize:
                self._cache.popitem(last=False)

    async def delete(self, key: K) -> bool:
        """Delete key from cache. Returns True if key was present."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> None:
        """Clear all entries from cache."""
        async with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def _cleanup_expired_sync(self) -> int:
        """Synchronous cleanup of expired entries."""
        expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
        for k in expired_keys:
            del self._cache[k]
        return len(expired_keys)

    async def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count cleaned."""
        async with self._lock:
            return self._cleanup_expired_sync()

    async def start_cleanup_task(self, interval: float = 60.0) -> None:
        """Start background cleanup task for expired entries."""
        if self._cleanup_running:
            return

        self._cleanup_running = True

        async def _cleanup_loop():
            while self._cleanup_running:
                try:
                    await asyncio.sleep(interval)
                    cleaned = await self.cleanup_expired()
                    if cleaned > 0:
                        logger.debug("Cache '%s' cleaned %d expired entries", self.name, cleaned)
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    logger.warning("Cache cleanup error: %s", exc)

        self._cleanup_task = asyncio.create_task(_cleanup_loop())

    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        if not self._cleanup_running:
            return

        self._cleanup_running = False

        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            finally:
                self._cleanup_task = None

    def __len__(self) -> int:
        """Return the number of items in the cache."""
        return len(self._cache)

    def __contains__(self, key: K) -> bool:
        """Check if key exists and is not expired. Thread-safe."""
        entry = self._cache.get(key)
        if entry is None:
            return False
        if entry.is_expired():
            return False
        return True


# Global cache instances — sized/TTLed from config.CacheSettings so
# RYLIOX_CACHE__* environment overrides apply.
_cache_settings = config.SETTINGS.cache
_book_metadata_cache: LRUCache[str, dict] = LRUCache(
    maxsize=_cache_settings.books_maxsize,
    default_ttl=float(_cache_settings.books_ttl),
    name="book_metadata",
)
_chapter_list_cache: LRUCache[str, list] = LRUCache(
    maxsize=_cache_settings.chapters_maxsize,
    default_ttl=float(_cache_settings.chapters_ttl),
    name="chapter_list",
)
_search_results_cache: LRUCache[str, list] = LRUCache(
    maxsize=_cache_settings.search_maxsize,
    default_ttl=float(_cache_settings.search_ttl),
    name="search_results",
)


def get_book_metadata_cache() -> LRUCache[str, dict]:
    """Get the global book metadata cache."""
    return _book_metadata_cache


def get_chapter_list_cache() -> LRUCache[str, list]:
    """Get the global chapter list cache."""
    return _chapter_list_cache


def get_search_results_cache() -> LRUCache[str, list]:
    """Get the global search results cache."""
    return _search_results_cache


async def clear_all_caches() -> None:
    """Clear all global caches (books, chapters, search)."""
    await get_book_metadata_cache().clear()
    await get_chapter_list_cache().clear()
    await get_search_results_cache().clear()


async def start_all_cleanup_tasks(interval: float = 60.0) -> None:
    """Start cleanup tasks for all global caches."""
    await get_book_metadata_cache().start_cleanup_task(interval)
    await get_chapter_list_cache().start_cleanup_task(interval)
    await get_search_results_cache().start_cleanup_task(interval)
    logger.info("Started cache cleanup tasks (interval=%.0fs)", interval)


async def stop_all_cleanup_tasks() -> None:
    """Stop all cleanup tasks."""
    await get_book_metadata_cache().stop_cleanup_task()
    await get_chapter_list_cache().stop_cleanup_task()
    await get_search_results_cache().stop_cleanup_task()
    logger.info("Stopped cache cleanup tasks")
