"""Runtime configuration.

Precedence (highest -> lowest):
  1. Environment variables
  2. .env file
  3. Built-in defaults
"""

from __future__ import annotations

import logging
import secrets
from pathlib import Path
from types import MappingProxyType
from typing import Final

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

BASE_DIR: Final = Path(__file__).resolve().parent
_RUNTIME_DATA_FALLBACK_DIR: Final[Path] = BASE_DIR / ".runtime_data"
_RUNTIME_OUTPUT_FALLBACK_DIR: Final[Path] = BASE_DIR / ".runtime_output"

_FALLBACK_USER_AGENTS: Final[tuple[str, ...]] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_6) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
    "Gecko/20100101 Firefox/125.0",
)

_PROTECTED_HEADERS: Final[frozenset[str]] = frozenset(
    {
        "user-agent",
        "accept",
        "accept-encoding",
        "accept-language",
    }
)


def _to_absolute_path(path: Path) -> Path:
    return path if path.is_absolute() else (BASE_DIR / path)


def _dir_is_writable(path: Path) -> bool:
    try:
        if path.exists() and not path.is_dir():
            return False
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".rw_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _resolve_runtime_dir(
    configured: Path | None,
    *,
    default: Path,
    fallback: Path,
    label: str,
) -> Path:
    candidate = _to_absolute_path(configured or default)
    if _dir_is_writable(candidate):
        return candidate

    fallback_path = _to_absolute_path(fallback)
    if _dir_is_writable(fallback_path):
        logger.warning("%s is not writable at %s. Using %s.", label, candidate, fallback_path)
        return fallback_path

    logger.warning("%s is not writable at %s.", label, candidate)
    return candidate


def _resolve_runtime_file(
    configured: Path | None,
    *,
    default: Path,
    fallback_dir: Path,
    label: str,
) -> Path:
    candidate = _to_absolute_path(configured or default)
    if _dir_is_writable(candidate.parent):
        return candidate

    fallback_path = fallback_dir / candidate.name
    if _dir_is_writable(fallback_path.parent):
        logger.warning(
            "%s parent is not writable at %s. Using %s.",
            label,
            candidate.parent,
            fallback_path,
        )
        return fallback_path

    logger.warning("%s parent is not writable at %s.", label, candidate.parent)
    return candidate


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    base_url: str = Field(
        default="https://learning.oreilly.com", validation_alias="BASE_URL"
    )
    request_delay: float = Field(default=0.5, ge=0.0, validation_alias="REQUEST_DELAY")
    request_timeout: int = Field(default=30, ge=1, validation_alias="REQUEST_TIMEOUT")
    request_retries: int = Field(default=2, ge=0, validation_alias="REQUEST_RETRIES")
    request_retry_backoff: float = Field(
        default=0.5, ge=0.0, validation_alias="REQUEST_RETRY_BACKOFF"
    )

    output_dir: Path | None = Field(default=None, validation_alias="OUTPUT_DIR")
    data_dir: Path | None = Field(default=None, validation_alias="DATA_DIR")
    cookies_file: Path | None = Field(default=None, validation_alias="COOKIES_FILE")
    session_db_file: Path | None = Field(
        default=None, validation_alias="SESSION_DB_FILE"
    )

    user_agent: str | None = Field(default=None, validation_alias="USER_AGENT")
    enable_fake_ua: bool = Field(
        default=False, validation_alias="ENABLE_FAKE_USERAGENT"
    )
    extra_headers: dict[str, str] | None = Field(
        default=None, validation_alias="HEADERS"
    )
    accept: str = Field(
        default="text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        validation_alias="ACCEPT",
    )
    accept_encoding: str = Field(
        default="gzip, deflate", validation_alias="ACCEPT_ENCODING"
    )
    accept_language: str = Field(
        default="en-US,en;q=0.5", validation_alias="ACCEPT_LANGUAGE"
    )

    @field_validator("base_url", mode="after")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @field_validator("extra_headers", mode="after")
    @classmethod
    def _reject_protected_header_overrides(
        cls, v: dict[str, str] | None
    ) -> dict[str, str] | None:
        """Reject overrides for protected headers."""
        if not v:
            return v
        conflicts = {k for k in v if k.lower() in _PROTECTED_HEADERS}
        if conflicts:
            raise ValueError(
                f"extra_headers no puede sobreescribir headers protegidos: {sorted(conflicts)}. "
                "Usa USER_AGENT, ACCEPT, ACCEPT_ENCODING o ACCEPT_LANGUAGE en su lugar."
            )
        return v

    @model_validator(mode="after")
    def _warn_if_env_missing(self) -> "Settings":
        env_path = BASE_DIR / ".env"
        if not env_path.exists():
            logger.debug(
                ".env no encontrado en %s — usando solo variables de entorno y defaults.",
                env_path,
            )
        return self


SETTINGS: Final = Settings()

OUTPUT_DIR: Final[Path] = _resolve_runtime_dir(
    SETTINGS.output_dir,
    default=BASE_DIR / "output",
    fallback=_RUNTIME_OUTPUT_FALLBACK_DIR,
    label="OUTPUT_DIR",
)
DATA_DIR: Final[Path] = _resolve_runtime_dir(
    SETTINGS.data_dir,
    default=BASE_DIR / "data",
    fallback=_RUNTIME_DATA_FALLBACK_DIR,
    label="DATA_DIR",
)
COOKIES_FILE: Final[Path] = _resolve_runtime_file(
    SETTINGS.cookies_file,
    default=DATA_DIR / "cookies.json",
    fallback_dir=DATA_DIR,
    label="COOKIES_FILE",
)
SESSION_DB_FILE: Final[Path] = _resolve_runtime_file(
    SETTINGS.session_db_file,
    default=DATA_DIR / "session.sqlite3",
    fallback_dir=DATA_DIR,
    label="SESSION_DB_FILE",
)

BASE_URL: Final[str] = SETTINGS.base_url
API_V1: Final[str] = f"{BASE_URL}/api/v1"
API_V2: Final[str] = f"{BASE_URL}/api/v2"
REQUEST_DELAY: Final[float] = SETTINGS.request_delay
REQUEST_TIMEOUT: Final[int] = SETTINGS.request_timeout
REQUEST_RETRIES: Final[int] = SETTINGS.request_retries
REQUEST_RETRY_BACKOFF: Final[float] = SETTINGS.request_retry_backoff


def _resolve_user_agent() -> str:
    """Resolve user-agent from explicit value, fake-useragent, or fallback list."""
    if ua := (SETTINGS.user_agent or "").strip():
        return ua

    if SETTINGS.enable_fake_ua:
        try:
            from fake_useragent import UserAgent

            candidate = UserAgent().random
            if isinstance(candidate, str) and candidate.strip().lower().startswith(
                "mozilla"
            ):
                return candidate.strip()
            logger.warning(
                "fake_useragent retorno un valor inesperado (%r), usando fallback.",
                candidate,
            )
        except Exception as exc:
            logger.warning("fake_useragent no disponible (%s), usando fallback.", exc)

    return secrets.choice(_FALLBACK_USER_AGENTS)

HEADERS: Final[MappingProxyType[str, str]] = MappingProxyType(
    {
        "Accept": SETTINGS.accept,
        "Accept-Encoding": SETTINGS.accept_encoding,
        "Accept-Language": SETTINGS.accept_language,
        "Referer": BASE_URL,
        "User-Agent": _resolve_user_agent(),
        **(SETTINGS.extra_headers or {}),
    }
)
