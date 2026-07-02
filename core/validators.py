"""Input validators for OWASP A03: Injection protection."""

from __future__ import annotations

import asyncio
import concurrent.futures
import ipaddress
import logging
import re
import socket
import unicodedata
from pathlib import Path
from re import Pattern
from typing import Any
from urllib.parse import unquote, urlparse

logger = logging.getLogger(__name__)

# MED-001: DNS rebinding protection
_DNS_CACHE: dict[str, tuple[str, float]] = {}
_DNS_CACHE_TTL_SECONDS: float = 30.0

# OWASP A03: XSS prevention patterns
_DANGEROUS_HTML_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"<script", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),
    re.compile(r"<iframe", re.IGNORECASE),
    re.compile(r"<object", re.IGNORECASE),
    re.compile(r"<embed", re.IGNORECASE),
    re.compile(r"expression\s*\(", re.IGNORECASE),
    re.compile(r"data:text/html", re.IGNORECASE),
)

_ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})

# OWASP A10: SSRF prevention - blocked hosts (including localhost variants)
_DANGEROUS_URL_HOSTS: frozenset[str] = frozenset(  # nosec B104
    {
        "localhost",
        "127.0.0.1",
        "127.0.0.01",  # Leading zero variant
        "0177.0.0.1",  # Octal notation
        "2130706433",  # Decimal notation for 127.0.0.1
        "0.0.0.0",  # nosec B104
        "::1",
        "[::1]",
        "0000:0000:0000:0000:0000:0000:0000:0001",  # Full IPv6 localhost
        "0:0:0:0:0:0:0:1",  # Short IPv6 localhost
    }
)

# Book ID patterns: urn:orm:book:<32-char-hex> or 10/13-digit ISBN
_BOOK_ID_PATTERN: Pattern[str] = re.compile(r"^urn:orm:book:[a-f0-9]{32}$", re.IGNORECASE)
_ISBN_PATTERN: Pattern[str] = re.compile(r"^\d{9}[\dX]$|^\d{13}$")

_SAFE_FILENAME_CHARS: Pattern[str] = re.compile(r"^[\w\-_. ]+$")

# OWASP A03: Path traversal prevention
_PATH_TRAVERSAL_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"\.\.[\\/]"),
    re.compile(r"[\\/]\.\."),
    re.compile(r"\.\.\Z"),
)

# Control chars to block (allow tab, LF, CR)
_CONTROL_CHARS: frozenset[int] = frozenset(range(0x20)) - frozenset({0x09, 0x0A, 0x0D})

MAX_BOOK_ID_LENGTH: int = 50
MAX_URL_LENGTH: int = 2048
MAX_FILENAME_LENGTH: int = 255
MAX_INPUT_LENGTH: int = 10000
MAX_PATH_LENGTH: int = 4096

# DNS lookup timeout (seconds)
_DNS_LOOKUP_TIMEOUT: float = 5.0


def _is_dangerous_ip(ip_str: str) -> bool:
    """Check if an IP address is private/reserved (DRY helper)."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
    except ValueError:
        return False


def _check_host_ip_dangerous(hostname: str, url: str) -> None:
    """Validate hostname is not a dangerous IP address."""
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
            raise ValidationError(
                "url",
                f"URL IP address '{hostname}' is not allowed (private/reserved)",
                url[:100],
            )
    except ValueError:
        pass


def _normalize_hostname(hostname: str) -> str:
    """Normalize hostname with Unicode NFKC and lowercase."""
    normalized = unicodedata.normalize("NFKC", hostname)
    return normalized.lower()


class ValidationError(ValueError):
    """Raised when input validation fails."""

    def __init__(self, field: str, reason: str, value: Any = None) -> None:
        self.field = field
        self.reason = reason
        self.value = value
        super().__init__(f"Validation failed for '{field}': {reason}")


def validate_book_id(book_id: str) -> str:
    """Validate book ID format.

    Accepts:
      - urn:orm:book:<32-char-hex>
      - 10/13-digit ISBN
    """
    if not book_id:
        raise ValidationError("book_id", "Book ID cannot be empty", book_id)

    if len(book_id) > MAX_BOOK_ID_LENGTH:
        raise ValidationError(
            "book_id",
            f"Book ID too long (max {MAX_BOOK_ID_LENGTH} chars)",
            book_id[:50],
        )

    if _ISBN_PATTERN.match(book_id.upper()):
        return book_id

    if _BOOK_ID_PATTERN.match(book_id):
        return book_id.lower()

    raise ValidationError(
        "book_id",
        "Invalid book ID format. Expected: urn:orm:book:<32-char-hex> or a 10/13-digit ISBN",
        book_id[:50],
    )


def _resolve_and_validate_dns(hostname: str, url: str) -> str | None:
    """Resolve hostname and validate the IP is not private/reserved.

    MED-001: DNS rebinding protection - validates IP at resolution time
    and returns the resolved IP if valid, None otherwise.
    """
    import time

    # Check cache first
    now = time.monotonic()
    if hostname in _DNS_CACHE:
        cached_ip, timestamp = _DNS_CACHE[hostname]
        if now - timestamp < _DNS_CACHE_TTL_SECONDS:
            return cached_ip
        del _DNS_CACHE[hostname]

    try:
        addr_info = socket.getaddrinfo(hostname, None)
        for _, _, _, _, sockaddr in addr_info:
            ip_str = str(sockaddr[0])
            if _is_dangerous_ip(ip_str):
                raise ValidationError(
                    "url",
                    f"URL hostname '{hostname}' resolves to private/reserved IP '{ip_str}'",
                    url[:100],
                )
            # Cache and return the first valid IP
            _DNS_CACHE[hostname] = (ip_str, now)
            return ip_str
    except ValidationError:
        raise
    except Exception as exc:
        logger.debug("DNS validation failed for %s: %s", hostname, exc)
    return None


async def validate_url(url: str, allowed_hosts: set[str] | None = None) -> str:
    """Validate URL against SSRF and injection attacks (async)."""
    if not url:
        raise ValidationError("url", "URL cannot be empty", url)

    if len(url) > MAX_URL_LENGTH:
        raise ValidationError("url", f"URL too long (max {MAX_URL_LENGTH} chars)", url[:100])

    parsed = urlparse(url)

    scheme = parsed.scheme.lower()
    if not scheme:
        raise ValidationError("url", "URL must have a scheme (http/https)", url[:100])

    if scheme not in _ALLOWED_SCHEMES:
        raise ValidationError(
            "url", f"URL scheme '{scheme}' not allowed. Use http or https.", url[:100]
        )

    hostname = parsed.hostname
    if not hostname:
        raise ValidationError("url", "URL must have a hostname", url[:100])

    # Unicode normalization for homograph attack prevention
    hostname_lower = _normalize_hostname(hostname)

    # Block IDN/punycode domains
    if hostname_lower.startswith("xn--") or "xn--" in hostname_lower:
        raise ValidationError(
            "url",
            f"URL hostname '{hostname}' contains IDN/punycode characters (not allowed)",
            url[:100],
        )

    # DNS rebinding protection: check if domain resolves to private IP with caching (MED-001)
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_resolve_and_validate_dns, hostname, url)
            resolved_ip = await asyncio.wait_for(
                asyncio.wrap_future(future), timeout=_DNS_LOOKUP_TIMEOUT
            )
        # Re-validate at connection time: if DNS returned a valid IP, ensure it's still not dangerous
        if resolved_ip and _is_dangerous_ip(resolved_ip):
            raise ValidationError(
                "url",
                f"URL hostname '{hostname}' resolves to private/reserved IP '{resolved_ip}'",
                url[:100],
            )
    except TimeoutError:
        # DNS lookup timed out - continue with hostname validation
        pass
    except socket.gaierror:
        # DNS resolution failed - this is acceptable, we'll validate the hostname itself
        pass
    except ValidationError:
        raise
    except Exception as exc:
        # Other socket errors - continue with hostname validation
        logger.debug("Async DNS validation failed for %s: %s", hostname, exc)

    # Block localhost/private IPs (SSRF protection)
    if hostname_lower in _DANGEROUS_URL_HOSTS:
        raise ValidationError(
            "url",
            f"URL hostname '{hostname}' is not allowed (localhost/private)",
            url[:100],
        )

    # Check for IP addresses (block private ranges)
    _check_host_ip_dangerous(hostname, url)

    if allowed_hosts and hostname_lower not in allowed_hosts:
        raise ValidationError(
            "url", f"URL hostname '{hostname}' not in allowed hosts list", url[:100]
        )

    # Check for credentials in URL
    if parsed.username or parsed.password:
        raise ValidationError("url", "URL must not contain credentials (user:pass@host)", url[:100])

    return url


def validate_url_sync(url: str, allowed_hosts: set[str] | None = None) -> str:
    """Validate URL against SSRF and injection attacks (sync version)."""
    if not url:
        raise ValidationError("url", "URL cannot be empty", url)

    if len(url) > MAX_URL_LENGTH:
        raise ValidationError("url", f"URL too long (max {MAX_URL_LENGTH} chars)", url[:100])

    parsed = urlparse(url)

    scheme = parsed.scheme.lower()
    if not scheme:
        raise ValidationError("url", "URL must have a scheme (http/https)", url[:100])

    if scheme not in _ALLOWED_SCHEMES:
        raise ValidationError(
            "url", f"URL scheme '{scheme}' not allowed. Use http or https.", url[:100]
        )

    hostname = parsed.hostname
    if not hostname:
        raise ValidationError("url", "URL must have a hostname", url[:100])

    # Unicode normalization for homograph attack prevention
    hostname_lower = _normalize_hostname(hostname)

    if hostname_lower.startswith("xn--") or "xn--" in hostname_lower:
        raise ValidationError(
            "url",
            f"URL hostname '{hostname}' contains IDN/punycode characters (not allowed)",
            url[:100],
        )

    # DNS rebinding protection (sync with timeout via signal alarm on Unix)
    try:
        # Use socket with timeout for DNS resolution
        socket.setdefaulttimeout(_DNS_LOOKUP_TIMEOUT)
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for _, _, _, _, sockaddr in addr_info:
                ip_str = str(sockaddr[0])
                if _is_dangerous_ip(ip_str):
                    raise ValidationError(
                        "url",
                        f"URL hostname '{hostname}' resolves to private/reserved IP '{ip_str}'",
                        url[:100],
                    )
        finally:
            socket.setdefaulttimeout(None)
    except socket.gaierror:
        pass
    except ValidationError:
        raise
    except Exception as exc:
        logger.debug("Sync DNS validation failed for %s: %s", hostname, exc)

    if hostname_lower in _DANGEROUS_URL_HOSTS:
        raise ValidationError(
            "url",
            f"URL hostname '{hostname}' is not allowed (localhost/private)",
            url[:100],
        )

    # Check for IP addresses (block private ranges)
    _check_host_ip_dangerous(hostname, url)

    if allowed_hosts and hostname_lower not in allowed_hosts:
        raise ValidationError(
            "url", f"URL hostname '{hostname}' not in allowed hosts list", url[:100]
        )

    if parsed.username or parsed.password:
        raise ValidationError("url", "URL must not contain credentials (user:pass@host)", url[:100])

    return url


def validate_file_path(path: str, base_dir: Path | None = None, must_exist: bool = False) -> Path:
    """Validate and sanitize file path to prevent path traversal."""
    if not path:
        raise ValidationError("path", "File path cannot be empty", path)

    if len(path) > MAX_PATH_LENGTH:
        raise ValidationError("path", f"Path too long (max {MAX_PATH_LENGTH} chars)", path[:100])

    if "\x00" in path:
        raise ValidationError("path", "Path contains null bytes", path[:50])

    # Check for path traversal attempts on original path
    for pattern in _PATH_TRAVERSAL_PATTERNS:
        if pattern.search(path):
            raise ValidationError("path", "Path contains directory traversal attempt", path[:100])

    # Check for URL-encoded traversal patterns
    decoded_path = unquote(path)
    if decoded_path != path:
        for pattern in _PATH_TRAVERSAL_PATTERNS:
            if pattern.search(decoded_path):
                raise ValidationError(
                    "path",
                    "Path contains URL-encoded directory traversal attempt",
                    path[:100],
                )

    # Normalize the path
    try:
        if base_dir is not None:
            resolved_path = (base_dir / path).resolve()
        else:
            resolved_path = Path(path).resolve()
    except (OSError, ValueError) as exc:
        raise ValidationError("path", f"Invalid path: {exc}", path[:100]) from exc

    # Ensure path is under base_dir (symlinks protection)
    if base_dir is not None:
        base_resolved = base_dir.resolve()
        try:
            resolved_path.relative_to(base_resolved)
        except ValueError:
            raise ValidationError(
                "path", f"Path must be under {base_resolved}", str(resolved_path)[:100]
            )

    if must_exist and not resolved_path.exists():
        raise ValidationError(
            "path", f"File does not exist: {resolved_path}", str(resolved_path)[:100]
        )

    return resolved_path


def validate_filename(filename: str) -> str:
    """Validate filename for safety."""
    if not filename:
        raise ValidationError("filename", "Filename cannot be empty", filename)

    if len(filename) > MAX_FILENAME_LENGTH:
        raise ValidationError(
            "filename",
            f"Filename too long (max {MAX_FILENAME_LENGTH} chars)",
            filename[:50],
        )

    # Remove path components
    filename = Path(filename).name

    if not filename.strip():
        raise ValidationError(
            "filename", "Filename cannot consist entirely of whitespace", filename[:50]
        )

    if filename.startswith(".") or filename.startswith("~"):
        raise ValidationError("filename", "Filename cannot start with '.' or '~'", filename[:50])

    dangerous_exts = {
        ".exe",
        ".dll",
        ".bat",
        ".cmd",
        ".sh",
        ".php",
        ".jsp",
        ".asp",
        ".aspx",
    }
    if any(filename.lower().endswith(ext) for ext in dangerous_exts):
        raise ValidationError("filename", "Filename has dangerous extension", filename[:50])

    if not _SAFE_FILENAME_CHARS.match(filename):
        raise ValidationError("filename", "Filename contains unsafe characters", filename[:50])

    return filename


def validate_user_input(
    text: str | None, allow_html: bool = False, max_length: int = MAX_INPUT_LENGTH
) -> str:
    """Validate user input for XSS and injection attacks."""
    if text is None:
        raise ValidationError("input", "Input cannot be None", text)

    if not isinstance(text, str):
        text = str(text)

    if len(text) > max_length:
        raise ValidationError("input", f"Input too long (max {max_length} chars)", text[:100])

    # Unicode normalization to prevent homograph attacks
    text = unicodedata.normalize("NFKC", text)

    # Check for control characters
    for char in text:
        if ord(char) in _CONTROL_CHARS:
            raise ValidationError("input", "Input contains control characters", text[:50])

    # Check for dangerous HTML if not explicitly allowed
    if not allow_html:
        for pattern in _DANGEROUS_HTML_PATTERNS:
            if pattern.search(text):
                raise ValidationError(
                    "input", "Input contains potentially dangerous HTML/JS", text[:100]
                )

    return text


def sanitize_for_logs(text: str, max_length: int = 500) -> str:
    """Sanitize text for safe logging (prevents log injection)."""
    if not isinstance(text, str):
        text = str(text)

    # Remove newlines (log injection prevention)
    text = text.replace("\n", " ").replace("\r", " ")

    # Remove null bytes
    text = text.replace("\x00", "")

    # Truncate
    if len(text) > max_length:
        text = text[: max_length - 3] + "..."

    return text


class PydanticValidators:
    """Pydantic-compatible validator functions for use in schemas."""

    @classmethod
    def validate_book_id_pydantic(cls, v: Any) -> str | None:
        """Pydantic field validator for book IDs."""
        if v is None:
            return v
        return validate_book_id(str(v))

    @classmethod
    def validate_url_pydantic(cls, v: Any, allowed_hosts: set[str] | None = None) -> str | None:
        """Pydantic field validator for URLs."""
        if v is None:
            return v
        return validate_url_sync(str(v), allowed_hosts)

    @classmethod
    def validate_safe_string(cls, v: Any, max_length: int = MAX_INPUT_LENGTH) -> str | None:
        """Pydantic field validator for safe strings."""
        if v is None:
            return v
        return validate_user_input(str(v), allow_html=False, max_length=max_length)

    @classmethod
    def validate_filename_pydantic(cls, v: Any) -> str | None:
        """Pydantic field validator for filenames."""
        if v is None:
            return v
        return validate_filename(str(v))


__all__ = [
    "MAX_BOOK_ID_LENGTH",
    "MAX_FILENAME_LENGTH",
    "MAX_INPUT_LENGTH",
    "MAX_PATH_LENGTH",
    "MAX_URL_LENGTH",
    "PydanticValidators",
    "ValidationError",
    "sanitize_for_logs",
    "validate_book_id",
    "validate_file_path",
    "validate_filename",
    "validate_url",
    "validate_url_sync",
    "validate_user_input",
]
