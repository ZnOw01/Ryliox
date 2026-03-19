"""Shared URL sanitization utilities."""

from __future__ import annotations

import ipaddress
import logging
from urllib.parse import urljoin, urlparse

import config

logger = logging.getLogger(__name__)


def _configured_base_host() -> str:
    try:
        return (urlparse(config.BASE_URL).hostname or "").lower()
    except ValueError:
        return ""


def _is_allowed_host(host: str) -> bool:
    base_host = _configured_base_host()
    return bool(base_host) and (host == base_host or host.endswith(f".{base_host}"))


def _is_blocked_host(host: str) -> bool:
    if not host:
        return True
    if host == "localhost" or host.endswith(".local"):
        return True

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False

    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
    )


def _normalize_candidate_url(raw_url: str, *, base_url: str = "") -> str:
    value = str(raw_url or "").strip()
    if not value or value.startswith("data:"):
        return ""
    if value.startswith("//"):
        return f"https:{value}"
    if value.startswith(("http://", "https://")):
        return value
    return urljoin(base_url or config.BASE_URL, value)


def is_safe_url(url: str) -> bool:
    """Return True if the URL is allowed for this app's remote fetches."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False

    if parsed.scheme not in {"http", "https"}:
        return False

    host = (parsed.hostname or "").lower()
    if _is_blocked_host(host):
        return False

    return _is_allowed_host(host)


def normalize_remote_url(raw_url: str, *, base_url: str = "") -> str:
    """Normalize a remote URL and return empty string if it is not allowed."""
    normalized = _normalize_candidate_url(raw_url, base_url=base_url)
    if not normalized:
        return ""
    return normalized if is_safe_url(normalized) else ""


def normalize_asset_url(base_url: str, asset_url: str) -> str:
    """Normalize an asset URL and return empty string if not allowed."""
    normalized = normalize_remote_url(asset_url, base_url=base_url)
    if not normalized:
        value = str(asset_url or "").strip()
        if value:
            logger.warning("Blocked asset URL outside allowed hosts: %s", value)
    return normalized


def sanitize_remote_url(raw_url: str, *, base_url: str = "") -> str:
    """Sanitize a remote URL and return empty string if not allowed."""
    return normalize_remote_url(raw_url, base_url=base_url)


def ensure_safe_asset_url(url: str) -> None:
    """Raise ValueError if the asset URL is not safe."""
    try:
        parsed = urlparse(str(url))
    except ValueError as exc:
        raise ValueError(f"Invalid asset URL: {url!r}") from exc

    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Unsupported asset URL scheme: {parsed.scheme!r}")

    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("Asset URL does not contain a hostname")

    if _is_blocked_host(host):
        raise ValueError(f"Blocked local or private asset host: {host}")

    if not _is_allowed_host(host):
        raise ValueError(f"Blocked asset host outside allowed hosts: {host}")
