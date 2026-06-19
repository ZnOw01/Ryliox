"""File system utilities: filename sanitization, slugification, accent removal."""

from __future__ import annotations

import re
import unicodedata
from typing import Final

# Windows reserved device names (case-insensitive, optionally with extension).
_WINDOWS_RESERVED: Final[frozenset[str]] = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)

_INVALID_FILENAME_CHARS: Final[re.Pattern[str]] = re.compile(r'[<>:"/\\|\x00-\x1f]')
_REMOVE_FILENAME_CHARS: Final[re.Pattern[str]] = re.compile(r"[?*]")
_WHITESPACE_RUN: Final[re.Pattern[str]] = re.compile(r"\s+")
_NON_SLUG: Final[re.Pattern[str]] = re.compile(r"[^a-z0-9]+")
_LEADING_DASH: Final[re.Pattern[str]] = re.compile(r"^-+")
_TRAILING_DASH: Final[re.Pattern[str]] = re.compile(r"-+$")
_LEADING_PATH_PREFIX: Final[re.Pattern[str]] = re.compile(r"^[\\/]+")

MAX_FILENAME_LENGTH: Final[int] = 200
MAX_SLUG_LENGTH: Final[int] = 100


def remove_accents(text: str) -> str:
    """Strip diacritics from ``text`` using NFKD decomposition."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _strip_control_chars(name: str) -> str:
    return "".join(ch for ch in name if ch.isprintable() and ch not in "\r\n\t")


def sanitize_filename(name: str | None) -> str:
    """Return a cross-platform safe filename.

    - Replaces OS-reserved characters with ``-``
    - Strips control characters
    - Strips path-traversal prefixes and leading separators
    - Appends ``_`` to Windows reserved device names
    - Falls back to ``"unnamed_file"`` for empty / None inputs
    """
    if name is None:
        return "unnamed_file"

    cleaned = _strip_control_chars(str(name))
    cleaned = cleaned.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    cleaned = _LEADING_PATH_PREFIX.sub("", cleaned)
    cleaned = cleaned.lstrip("~").lstrip("$")
    cleaned = cleaned.replace("..", "-")
    cleaned = cleaned.replace('"', "'")
    cleaned = _REMOVE_FILENAME_CHARS.sub("", cleaned)
    cleaned = _INVALID_FILENAME_CHARS.sub("-", cleaned)
    cleaned = _WHITESPACE_RUN.sub(" ", cleaned).strip().strip(".")
    cleaned = cleaned.strip()

    if not cleaned:
        return "unnamed_file"

    stem, dot, ext = cleaned.partition(".")
    if stem.upper() in _WINDOWS_RESERVED:
        stem = f"{stem}_"
        cleaned = f"{stem}{dot}{ext}" if ext else stem

    if len(cleaned) > MAX_FILENAME_LENGTH:
        cleaned = cleaned[:MAX_FILENAME_LENGTH].strip().strip(".")

    return cleaned or "unnamed_file"


def slugify(name: str | None) -> str:
    """Return a URL- and folder-friendly slug for ``name``."""
    if not name:
        return "unnamed-folder"

    slug = remove_accents(str(name)).lower()
    slug = slug.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    slug = _NON_SLUG.sub("-", slug)
    slug = _LEADING_DASH.sub("", slug)
    slug = _TRAILING_DASH.sub("", slug)

    if not slug:
        return "unnamed-folder"

    if len(slug) > MAX_SLUG_LENGTH:
        slug = slug[:MAX_SLUG_LENGTH].rstrip("-")

    return slug or "unnamed-folder"
