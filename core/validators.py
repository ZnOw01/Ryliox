"""Advanced input validators for OWASP A03: Injection protection.

Provides strict validation for:
- Book IDs (format urn:orm:book:*)
- URLs (whitelist-based validation)
- File paths (path traversal prevention)
- User input (XSS prevention, charset validation)
"""

from __future__ import annotations

import ipaddress
import re
import unicodedata
from pathlib import Path
from typing import Any, Pattern
from urllib.parse import urlparse

from pydantic import Field, field_validator


# OWASP XSS Prevention: Dangerous patterns
_DANGEROUS_HTML_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r'<script', re.IGNORECASE),
    re.compile(r'javascript:', re.IGNORECASE),
    re.compile(r'on\w+\s*=', re.IGNORECASE),  # onload, onclick, etc.
    re.compile(r'<iframe', re.IGNORECASE),
    re.compile(r'<object', re.IGNORECASE),
    re.compile(r'<embed', re.IGNORECASE),
    re.compile(r'expression\s*\(', re.IGNORECASE),  # CSS expressions
    re.compile(r'data:text/html', re.IGNORECASE),
)

# Allowed URL schemes
_ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})

# Dangerous URL patterns for SSRF prevention
_DANGEROUS_URL_HOSTS: frozenset[str] = frozenset({
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "[::1]",
})

# Book ID format pattern
_BOOK_ID_PATTERN: Pattern[str] = re.compile(
    r'^urn:orm:book:[a-f0-9]{32}$',
    re.IGNORECASE
)

# Safe filename characters
_SAFE_FILENAME_CHARS: Pattern[str] = re.compile(r'^[\w\-_. ]+$')

# Path traversal patterns
_PATH_TRAVERSAL_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r'\.\.[\\/]'),
    re.compile(r'[\\/]\.\.'),
    re.compile(r'\.\.\Z'),
)

# Control characters that should not appear in user input
_CONTROL_CHARS: frozenset[int] = frozenset(range(0x00, 0x20)) - frozenset({0x09, 0x0A, 0x0D})  # Exclude tab, LF, CR

# Maximum input lengths
MAX_BOOK_ID_LENGTH: int = 50
MAX_URL_LENGTH: int = 2048
MAX_FILENAME_LENGTH: int = 255
MAX_INPUT_LENGTH: int = 10000
MAX_PATH_LENGTH: int = 4096


class ValidationError(ValueError):
    """Raised when input validation fails."""
    
    def __init__(self, field: str, reason: str, value: Any = None) -> None:
        self.field = field
        self.reason = reason
        self.value = value
        super().__init__(f"Validation failed for '{field}': {reason}")


def validate_book_id(book_id: str) -> str:
    """Validate book ID format (urn:orm:book:*).
    
    Args:
        book_id: The book identifier to validate.
        
    Returns:
        The validated book ID (lowercase).
        
    Raises:
        ValidationError: If the book ID format is invalid.
    """
    if not book_id:
        raise ValidationError("book_id", "Book ID cannot be empty", book_id)
    
    if len(book_id) > MAX_BOOK_ID_LENGTH:
        raise ValidationError(
            "book_id", 
            f"Book ID too long (max {MAX_BOOK_ID_LENGTH} chars)",
            book_id[:50]
        )
    
    # Strict pattern matching
    if not _BOOK_ID_PATTERN.match(book_id):
        raise ValidationError(
            "book_id",
            "Invalid book ID format. Expected: urn:orm:book:<32-char-hex>",
            book_id[:50]
        )
    
    return book_id.lower()


def validate_url(url: str, allowed_hosts: set[str] | None = None) -> str:
    """Validate URL against SSRF and injection attacks.
    
    Args:
        url: The URL to validate.
        allowed_hosts: Optional set of allowed hostnames.
        
    Returns:
        The validated URL.
        
    Raises:
        ValidationError: If the URL is invalid or unsafe.
    """
    if not url:
        raise ValidationError("url", "URL cannot be empty", url)
    
    if len(url) > MAX_URL_LENGTH:
        raise ValidationError(
            "url",
            f"URL too long (max {MAX_URL_LENGTH} chars)",
            url[:100]
        )
    
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise ValidationError("url", f"Invalid URL format: {exc}", url[:100]) from exc
    
    # Check scheme
    scheme = parsed.scheme.lower()
    if not scheme:
        raise ValidationError("url", "URL must have a scheme (http/https)", url[:100])
    
    if scheme not in _ALLOWED_SCHEMES:
        raise ValidationError(
            "url",
            f"URL scheme '{scheme}' not allowed. Use http or https.",
            url[:100]
        )
    
    # Check hostname
    hostname = parsed.hostname
    if not hostname:
        raise ValidationError("url", "URL must have a hostname", url[:100])
    
    hostname_lower = hostname.lower()
    
    # Block localhost/private IPs (SSRF protection)
    if hostname_lower in _DANGEROUS_URL_HOSTS:
        raise ValidationError(
            "url",
            f"URL hostname '{hostname}' is not allowed (localhost/private)",
            url[:100]
        )
    
    # Check for IP addresses (block private ranges)
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
            raise ValidationError(
                "url",
                f"URL IP address '{hostname}' is not allowed (private/reserved)",
                url[:100]
            )
    except ValueError:
        # Not an IP address, that's fine
        pass
    
    # Check allowed hosts whitelist
    if allowed_hosts and hostname_lower not in allowed_hosts:
        raise ValidationError(
            "url",
            f"URL hostname '{hostname}' not in allowed hosts list",
            url[:100]
        )
    
    # Check for credentials in URL (security risk)
    if parsed.username or parsed.password:
        raise ValidationError(
            "url",
            "URL must not contain credentials (user:pass@host)",
            url[:100]
        )
    
    # Check for fragments (generally not needed for server requests)
    if parsed.fragment:
        raise ValidationError(
            "url",
            "URL must not contain fragment (#anchor)",
            url[:100]
        )
    
    return url


def validate_file_path(path: str, base_dir: Path | None = None, must_exist: bool = False) -> Path:
    """Validate and sanitize file path to prevent path traversal.
    
    Args:
        path: The file path to validate.
        base_dir: Optional base directory that the path must be under.
        must_exist: Whether the file must already exist.
        
    Returns:
        The validated, resolved Path object.
        
    Raises:
        ValidationError: If the path is invalid or unsafe.
    """
    if not path:
        raise ValidationError("path", "File path cannot be empty", path)
    
    if len(path) > MAX_PATH_LENGTH:
        raise ValidationError(
            "path",
            f"Path too long (max {MAX_PATH_LENGTH} chars)",
            path[:100]
        )
    
    # Check for null bytes
    if '\x00' in path:
        raise ValidationError("path", "Path contains null bytes", path[:50])
    
    # Check for path traversal attempts
    for pattern in _PATH_TRAVERSAL_PATTERNS:
        if pattern.search(path):
            raise ValidationError(
                "path",
                "Path contains directory traversal attempt",
                path[:100]
            )
    
    # Normalize the path
    try:
        resolved_path = Path(path).resolve()
    except (OSError, ValueError) as exc:
        raise ValidationError("path", f"Invalid path: {exc}", path[:100]) from exc
    
    # If base_dir specified, ensure path is under it
    if base_dir is not None:
        base_resolved = base_dir.resolve()
        try:
            # Check if resolved_path is under base_resolved
            resolved_path.relative_to(base_resolved)
        except ValueError:
            raise ValidationError(
                "path",
                f"Path must be under {base_resolved}",
                str(resolved_path)[:100]
            )
    
    # Check existence if required
    if must_exist and not resolved_path.exists():
        raise ValidationError(
            "path",
            f"File does not exist: {resolved_path}",
            str(resolved_path)[:100]
        )
    
    return resolved_path


def validate_filename(filename: str) -> str:
    """Validate filename for safety.
    
    Args:
        filename: The filename to validate.
        
    Returns:
        The sanitized filename.
        
    Raises:
        ValidationError: If the filename is unsafe.
    """
    if not filename:
        raise ValidationError("filename", "Filename cannot be empty", filename)
    
    if len(filename) > MAX_FILENAME_LENGTH:
        raise ValidationError(
            "filename",
            f"Filename too long (max {MAX_FILENAME_LENGTH} chars)",
            filename[:50]
        )
    
    # Remove path components
    filename = Path(filename).name
    
    # Check for dangerous patterns
    if filename.startswith('.') or filename.startswith('~'):
        raise ValidationError(
            "filename",
            "Filename cannot start with '.' or '~'",
            filename[:50]
        )
    
    # Check for dangerous extensions
    dangerous_exts = {'.exe', '.dll', '.bat', '.cmd', '.sh', '.php', '.jsp', '.asp', '.aspx'}
    if any(filename.lower().endswith(ext) for ext in dangerous_exts):
        raise ValidationError(
            "filename",
            "Filename has dangerous extension",
            filename[:50]
        )
    
    # Check characters
    if not _SAFE_FILENAME_CHARS.match(filename):
        raise ValidationError(
            "filename",
            "Filename contains unsafe characters",
            filename[:50]
        )
    
    return filename


def validate_user_input(text: str, allow_html: bool = False, max_length: int = MAX_INPUT_LENGTH) -> str:
    """Validate user input for XSS and injection attacks.
    
    Args:
        text: The user input to validate.
        allow_html: Whether to allow safe HTML (if False, blocks all HTML).
        max_length: Maximum allowed length.
        
    Returns:
        The sanitized text (unicode normalized).
        
    Raises:
        ValidationError: If the input contains dangerous content.
    """
    if text is None:
        return ""
    
    if not isinstance(text, str):
        text = str(text)
    
    # Length check
    if len(text) > max_length:
        raise ValidationError(
            "input",
            f"Input too long (max {max_length} chars)",
            text[:100]
        )
    
    # Unicode normalization to prevent homograph attacks
    text = unicodedata.normalize('NFKC', text)
    
    # Check for control characters
    for char in text:
        if ord(char) in _CONTROL_CHARS:
            raise ValidationError(
                "input",
                "Input contains control characters",
                text[:50]
            )
    
    # Check for dangerous HTML if not explicitly allowed
    if not allow_html:
        for pattern in _DANGEROUS_HTML_PATTERNS:
            if pattern.search(text):
                raise ValidationError(
                    "input",
                    "Input contains potentially dangerous HTML/JS",
                    text[:100]
                )
    
    return text


def sanitize_for_logs(text: str, max_length: int = 500) -> str:
    """Sanitize text for safe logging (prevents log injection).
    
    Args:
        text: The text to sanitize.
        max_length: Maximum length for logging.
        
    Returns:
        Sanitized text safe for logging.
    """
    if not isinstance(text, str):
        text = str(text)
    
    # Remove newlines (log injection prevention)
    text = text.replace('\n', ' ').replace('\r', ' ')
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Truncate
    if len(text) > max_length:
        text = text[:max_length - 3] + '...'
    
    return text


# Pydantic-compatible validators
class PydanticValidators:
    """Pydantic-compatible validator functions for use in schemas."""
    
    @classmethod
    def validate_book_id_pydantic(cls, v: Any) -> str:
        """Pydantic field validator for book IDs."""
        if v is None:
            return v
        return validate_book_id(str(v))
    
    @classmethod
    def validate_url_pydantic(cls, v: Any, allowed_hosts: set[str] | None = None) -> str:
        """Pydantic field validator for URLs."""
        if v is None:
            return v
        return validate_url(str(v), allowed_hosts)
    
    @classmethod
    def validate_safe_string(cls, v: Any, max_length: int = MAX_INPUT_LENGTH) -> str:
        """Pydantic field validator for safe strings."""
        if v is None:
            return v
        return validate_user_input(str(v), allow_html=False, max_length=max_length)
    
    @classmethod
    def validate_filename_pydantic(cls, v: Any) -> str:
        """Pydantic field validator for filenames."""
        if v is None:
            return v
        return validate_filename(str(v))


# Re-export common patterns
__all__ = [
    "ValidationError",
    "validate_book_id",
    "validate_url",
    "validate_file_path",
    "validate_filename",
    "validate_user_input",
    "sanitize_for_logs",
    "PydanticValidators",
    "MAX_BOOK_ID_LENGTH",
    "MAX_URL_LENGTH",
    "MAX_FILENAME_LENGTH",
    "MAX_INPUT_LENGTH",
    "MAX_PATH_LENGTH",
]
