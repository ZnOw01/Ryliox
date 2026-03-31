"""In-memory LRU cache with TTL support for Ryliox.

Provides caching utilities for:
- Book metadata
- Chapter lists
- HTTP responses
- Computed data
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Generic, TypeVar, cast

logger = logging.getLogger(__name__)

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


@dataclass
class CacheEntry(Generic[T]):
    """A cache entry with TTL support."""

    value: T
    created_at: float = field(default_factory=time.monotonic)
    expires_at: float | None = None
    access_count: int = 0

    def is_expired(self) -> bool:
        """Check if the entry has expired."""
        if self.expires_at is None:
            return False
        return time.monotonic() > self.expires_at

    def touch(self) -> None:
        """Increment access count."""
        self.access_count += 1


class LRUCache(Generic[K, V]):
    """Thread-safe LRU cache with TTL support.

    Features:
    - Least Recently Used eviction
    - Time-based expiration (TTL)
    - Hit/miss statistics
    - Optional async support
    - Background cleanup task
    """

    def __init__(
        self,
        maxsize: int = 128,
        default_ttl: float | None = None,
        name: str = "default",
    ):
        """Initialize LRU cache.

        Args:
            maxsize: Maximum number of items to store
            default_ttl: Default TTL in seconds for entries
            name: Cache name for logging
        """
        self.maxsize = max(1, int(maxsize))
        self.default_ttl = default_ttl
        self.name = name
        self._cache: OrderedDict[K, CacheEntry[V]] = OrderedDict()
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0
        self._cleanup_task: asyncio.Task | None = None

    async def get(self, key: K) -> V | None:
        """Get a value from the cache.

        Returns None if not found or expired.
        Updates access order on hit.
        """
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.touch()
            self._hits += 1
            return entry.value

    async def set(
        self, key: K, value: V, ttl: float | None = None, allow_update: bool = True
    ) -> None:
        """Set a value in the cache.

        Args:
            key: Cache key
            value: Value to store
            ttl: TTL in seconds (overrides default_ttl)
            allow_update: Whether to update existing entries
        """
        async with self._lock:
            if key in self._cache and not allow_update:
                return

            expires_at = None
            if ttl is not None:
                expires_at = time.monotonic() + ttl
            elif self.default_ttl is not None:
                expires_at = time.monotonic() + self.default_ttl

            entry = CacheEntry(value=value, expires_at=expires_at)

            # If key exists, remove it first to update position
            if key in self._cache:
                del self._cache[key]

            # Add to end (most recently used)
            self._cache[key] = entry

            # Evict oldest if over capacity
            while len(self._cache) > self.maxsize:
                self._cache.popitem(last=False)

    async def delete(self, key: K) -> bool:
        """Delete a key from the cache. Returns True if key was present."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> None:
        """Clear all entries from the cache."""
        async with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    async def invalidate_by_prefix(self, prefix: str) -> int:
        """Invalidate all keys starting with prefix. Returns count deleted."""
        async with self._lock:
            keys_to_delete = [
                k for k in self._cache.keys() if str(k).startswith(prefix)
            ]
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
        """Synchronous cleanup of expired entries. Returns count cleaned."""
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

        async def _cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(interval)
                    cleaned = await self.cleanup_expired()
                    if cleaned > 0:
                        logger.debug(
                            "Cache '%s' cleaned %d expired entries", self.name, cleaned
                        )
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    logger.warning("Cache cleanup error: %s", exc)

        self._cleanup_task = asyncio.create_task(_cleanup_loop())

    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    def __len__(self) -> int:
        """Return current cache size."""
        return len(self._cache)

    def __contains__(self, key: K) -> bool:
        """Check if key exists and is not expired."""
        entry = self._cache.get(key)
        if entry is None:
            return False
        if entry.is_expired():
            return False
        return True


class SimpleSyncLRUCache(Generic[K, V]):
    """Synchronous LRU cache for use in sync contexts.

    This is a simplified version without async support,
    suitable for use in synchronous code paths.
    """

    def __init__(self, maxsize: int = 128, default_ttl: float | None = None):
        self.maxsize = max(1, int(maxsize))
        self.default_ttl = default_ttl
        self._cache: OrderedDict[K, CacheEntry[V]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, key: K) -> V | None:
        """Get value from cache."""
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

    def set(
        self, key: K, value: V, ttl: float | None = None, allow_update: bool = True
    ) -> None:
        """Set value in cache."""
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
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        """Clear cache."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def cleanup_expired(self) -> int:
        """Clean expired entries."""
        expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
        for k in expired_keys:
            del self._cache[k]
        return len(expired_keys)

    def get_stats(self) -> dict[str, Any]:
        """Get cache stats."""
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
    """Decorator to cache async function results.

    Args:
        cache_instance: LRUCache instance to use
        key_func: Function to generate cache key from arguments
        ttl: TTL in seconds (overrides cache default)

    Example:
        cache = LRUCache[str, dict](maxsize=100)

        @cached(cache, key_func=lambda book_id: f"book:{book_id}")
        async def fetch_book(book_id: str) -> dict:
            return await api.get_book(book_id)
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default: hash of args and kwargs
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = hashlib.sha256("|".join(key_parts).encode()).hexdigest()[
                    :32
                ]

            # Try cache first
            cached_value = await cache_instance.get(cache_key)
            if cached_value is not None:
                logger.debug("Cache hit for %s (key=%s)", func.__name__, cache_key)
                return cached_value

            # Execute function
            result = await func(*args, **kwargs)

            # Store in cache
            await cache_instance.set(cache_key, result, ttl=ttl)
            logger.debug("Cache miss for %s (key=%s)", func.__name__, cache_key)

            return result

        # Attach cache methods for direct access
        wrapper.cache = cache_instance  # type: ignore
        wrapper.cache_key = (
            lambda *a, **kw: (  # type: ignore
                key_func(*a, **kw)
                if key_func
                else hashlib.sha256(
                    "|".join(
                        [func.__name__]
                        + [str(arg) for arg in a]
                        + [f"{k}={v}" for k, v in sorted(kw.items())]
                    ).encode()
                ).hexdigest()[:32]
            )
        )

        return wrapper

    return decorator


def make_cache_key(*args: Any, **kwargs: Any) -> str:
    """Generate a deterministic cache key from arguments."""
    key_parts = []
    key_parts.extend(str(arg) for arg in args)
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    return hashlib.sha256("|".join(key_parts).encode()).hexdigest()[:32]


# Global cache instances for common use cases
_book_metadata_cache: LRUCache[str, dict] | None = None
_chapter_list_cache: LRUCache[str, list] | None = None
_search_results_cache: LRUCache[str, list] | None = None


def get_book_metadata_cache() -> LRUCache[str, dict]:
    """Get or create the global book metadata cache."""
    global _book_metadata_cache
    if _book_metadata_cache is None:
        _book_metadata_cache = LRUCache(
            maxsize=256,
            default_ttl=3600.0,
            name="book_metadata",  # 1 hour
        )
    return _book_metadata_cache


def get_chapter_list_cache() -> LRUCache[str, list]:
    """Get or create the global chapter list cache."""
    global _chapter_list_cache
    if _chapter_list_cache is None:
        _chapter_list_cache = LRUCache(
            maxsize=128,
            default_ttl=1800.0,
            name="chapter_list",  # 30 minutes
        )
    return _chapter_list_cache


def get_search_results_cache() -> LRUCache[str, list]:
    """Get or create the global search results cache."""
    global _search_results_cache
    if _search_results_cache is None:
        _search_results_cache = LRUCache(
            maxsize=64,
            default_ttl=300.0,
            name="search_results",  # 5 minutes
        )
    return _search_results_cache


async def invalidate_book_cache(book_id: str) -> int:
    """Invalidate all cached data for a specific book.

    Returns the total number of entries invalidated.
    """
    book_cache = get_book_metadata_cache()
    chapter_cache = get_chapter_list_cache()

    book_deleted = await book_cache.delete(f"book:{book_id}")
    chapters_deleted = await chapter_cache.delete(f"chapters:{book_id}")

    # Also invalidate by prefix for any related entries
    book_prefix = await book_cache.invalidate_by_prefix(f"book:{book_id}:")
    chapter_prefix = await chapter_cache.invalidate_by_prefix(f"chapters:{book_id}:")

    total = sum([book_deleted, chapters_deleted, book_prefix, chapter_prefix])
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
