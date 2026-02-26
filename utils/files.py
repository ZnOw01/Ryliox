"""File system utilities: filename sanitization and slug generation."""

from __future__ import annotations

import re
import unicodedata

_FILENAME_CHAR_MAP: dict[int, str | None] = str.maketrans(
    {
        "/": "-",
        "\\": "-",
        ":": "-",
        "|": "-",
        "?": None,
        "*": None,
        '"': "'",
        "<": None,
        ">": None,
    }
)

_WINDOWS_RESERVED = re.compile(
    r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])\s*(\.|$)",
    re.IGNORECASE,
)

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")

_SLUG_QUOTES_RE = re.compile(r"['\"]")
_SLUG_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

_MAX_FILENAME_BYTES = 240
_MAX_SLUG_CHARS = 100  # ASCII puro tras remove_accents → chars == bytes


def remove_accents(text: str) -> str:
    """Elimina tildes y diacríticos, devolviendo una cadena ASCII segura.

    Args:
        text: Cadena de entrada. No acepta None; usar ``str(value)`` antes si es necesario.

    Examples:
        >>> remove_accents("Ñoño café")
        'Nono cafe'
        >>> remove_accents("über")
        'uber'
    """
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", "ignore").decode("ascii")


def _truncate_to_bytes(text: str, max_bytes: int) -> str:
    """Trunca *text* a *max_bytes* bytes UTF-8 sin cortar caracteres multibyte."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def _fix_windows_reserved(name: str) -> str:
    """Añade sufijo ``_`` antes de la extensión si *name* es un nombre reservado de Windows.

    Examples:
        >>> _fix_windows_reserved("CON")
        'CON_'
        >>> _fix_windows_reserved("CON.txt")
        'CON_.txt'
        >>> _fix_windows_reserved("con ")
        'con _'
    """
    if not _WINDOWS_RESERVED.match(name):
        return name
    dot_pos = name.find(".")
    if dot_pos == -1:
        return name.rstrip() + "_"
    return name[:dot_pos].rstrip() + "_" + name[dot_pos:]


def sanitize_filename(name: str | None) -> str:
    """Retorna un nombre de archivo seguro para Windows, macOS y Linux.

    Examples:
        >>> sanitize_filename("My: File?.txt")
        'My- File.txt'
        >>> sanitize_filename("CON.txt")
        'CON_.txt'
        >>> sanitize_filename(None)
        'unnamed_file'
        >>> sanitize_filename("   ...   ")
        'unnamed_file'
    """
    name = "" if name is None else str(name)

    name = _CONTROL_CHARS_RE.sub("", name)

    name = name.translate(_FILENAME_CHAR_MAP)

    name = " ".join(name.split()).strip(".")

    name = _fix_windows_reserved(name)

    name = _truncate_to_bytes(name, _MAX_FILENAME_BYTES).strip().strip(".")

    return name or "unnamed_file"


def slugify(name: str | None) -> str:
    """Convierte *name* en un slug ASCII apto para URLs y rutas de carpeta.

    Tras ``remove_accents`` el resultado es ASCII puro, por lo que el límite
    de caracteres equivale al límite de bytes.

    Examples:
        >>> slugify("¡Héroe del Mañana!")
        'heroe-del-manana'
        >>> slugify("  Multiple   Spaces  ")
        'multiple-spaces'
        >>> slugify(None)
        'unnamed-folder'
    """
    text = remove_accents("" if name is None else str(name)).lower()
    text = _SLUG_QUOTES_RE.sub("", text)
    text = _SLUG_NON_ALNUM_RE.sub("-", text).strip("-")

    if len(text) > _MAX_SLUG_CHARS:
        text = text[:_MAX_SLUG_CHARS].rstrip("-")

    return text or "unnamed-folder"
