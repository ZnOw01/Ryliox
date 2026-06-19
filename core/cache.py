"""In-memory LRU cache with TTL support."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from functools import wraps
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with TTL support."""

    value: T
    created_at: float = field(default_factory=time.monotonic)
    expires_at: float | None = None
    access_count: int = 0

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.monotonic() > self.expires_at

    def touch(self) -> None:
        self.access_count += 1


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
            entry.touch()
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

    async def invalidate_by_prefix(self, prefix: str) -> int:
        """Invalidate all keys starting with prefix. Returns count deleted."""
        async with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if str(k).startswith(prefix)]
            for k in keys_to_delete:
                del self._cache[k]
            return len(keys_to_delete)

    async def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        async with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0.0
            return {
                "name": self.name,
                "size": len(self._cache),
                "maxsize": self.maxsize,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 4),
                "utilization": round(len(self._cache) / self.maxsize, 4),
            }

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
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if entry.is_expired():
                return False
            return True


class SimpleSyncLRUCache(Generic[K, V]):
    """Synchronous LRU cache for use in sync contexts."""

    def __init__(self, maxsize: int = 128, default_ttl: float | None = None):
        if not isinstance(maxsize, int) or maxsize < 1:
            raise ValueError(f"maxsize must be a positive integer, got {maxsize!r}")
        self.maxsize = maxsize
        self.default_ttl = default_ttl
        self._cache: OrderedDict[K, CacheEntry[V]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: K) -> V | None:
        """Get value from cache."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None

            self._cache.move_to_end(key)
            entry.touch()
            self._hits += 1
            return entry.value

    def set(self, key: K, value: V, ttl: float | None = None, allow_update: bool = True) -> None:
        """Set value in cache."""
        with self._lock:
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

    def delete(self, key: K) -> bool:
        """Delete key from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear cache."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def cleanup_expired(self) -> int:
        """Clean expired entries."""
        with self._lock:
            expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
            for k in expired_keys:
                del self._cache[k]
            return len(expired_keys)

    def get_stats(self) -> dict[str, Any]:
        """Get cache stats."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0.0
            return {
                "size": len(self._cache),
                "maxsize": self.maxsize,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 4),
            }


def cached(
    cache_instance: LRUCache[Any, Any],
    key_func: Callable[..., str] | None = None,
    ttl: float | None = None,
):
    """Decorator to cache async function results."""
    _key_delim = "\x00"

    def _make_key(func_name: str, args: tuple, kwargs: dict) -> str:
        key_parts = [func_name]
        key_parts.extend(str(arg) for arg in args)
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        return hashlib.sha256(_key_delim.join(key_parts).encode()).hexdigest()[:32]

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if not asyncio.iscoroutinefunction(func):
            raise TypeError(
                f"@cached decorator only supports async functions. '{func.__name__}' is not a coroutine function."
            )

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = _make_key(func.__name__, args, kwargs)

            cached_value = await cache_instance.get(cache_key)
            if cached_value is not None:
                logger.debug("Cache hit for %s (key=%s)", func.__name__, cache_key)
                return cached_value

            result = await func(*args, **kwargs)
            await cache_instance.set(cache_key, result, ttl=ttl)
            logger.debug("Cache miss for %s (key=%s)", func.__name__, cache_key)

            return result

        wrapper.cache = cache_instance
        wrapper.cache_key = lambda *a, **kw: (
            key_func(*a, **kw) if key_func else _make_key(func.__name__, a, kw)
        )

        return wrapper

    return decorator


def make_cache_key(*args: Any, **kwargs: Any) -> str:
    """Generate a deterministic cache key from arguments."""
    _key_delim = "\x00"
    key_parts = []
    key_parts.extend(str(arg) for arg in args)
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    return hashlib.sha256(_key_delim.join(key_parts).encode()).hexdigest()[:32]


# Global cache instances
_book_metadata_cache: LRUCache[str, dict] = LRUCache(
    maxsize=256,
    default_ttl=3600.0,
    name="book_metadata",
)
_chapter_list_cache: LRUCache[str, list] = LRUCache(
    maxsize=128,
    default_ttl=1800.0,
    name="chapter_list",
)
_search_results_cache: LRUCache[str, list] = LRUCache(
    maxsize=64,
    default_ttl=300.0,
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


async def invalidate_book_cache(book_id: str) -> int:
    """Invalidate all cached data for a specific book."""
    book_cache = get_book_metadata_cache()
    chapter_cache = get_chapter_list_cache()

    book_deleted = await book_cache.delete(f"book:{book_id}")
    book_prefix = await book_cache.invalidate_by_prefix(f"book:{book_id}:")
    chapters_deleted = await chapter_cache.delete(f"chapters:{book_id}")
    chapter_prefix = await chapter_cache.invalidate_by_prefix(f"chapters:{book_id}:")

    total = book_deleted + book_prefix + chapters_deleted + chapter_prefix
    if total > 0:
        logger.info("Invalidated %d cache entries for book %s", total, book_id)
    return total


async def get_cache_stats() -> dict[str, Any]:
    """Get statistics for all global caches."""
    return {
        "book_metadata": await get_book_metadata_cache().get_stats(),
        "chapter_list": await get_chapter_list_cache().get_stats(),
        "search_results": await get_search_results_cache().get_stats(),
    }


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
