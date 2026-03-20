"""Runtime configuration.

Precedence (highest -> lowest):
  1. Environment variables
  2. .env file
  3. Built-in defaults
"""

from __future__ import annotations

import logging
import os
import secrets
import sys
from pathlib import Path
from types import MappingProxyType, ModuleType
from typing import Any, Final

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
_RUNTIME_EXPORTS: Final[frozenset[str]] = frozenset(
    {
        "SETTINGS",
        "OUTPUT_DIR",
        "DATA_DIR",
        "COOKIES_FILE",
        "SESSION_DB_FILE",
        "BASE_URL",
        "API_V1",
        "API_V2",
        "REQUEST_DELAY",
        "REQUEST_TIMEOUT",
        "REQUEST_RETRIES",
        "REQUEST_RETRY_BACKOFF",
        "HEADERS",
    }
)

_RUNTIME_VALUES: dict[str, Any] | None = None


def _to_absolute_path(path: Path) -> Path:
    return path if path.is_absolute() else (BASE_DIR / path)


def _nearest_existing_directory(path: Path) -> Path | None:
    current = path
    while True:
        if current.exists():
            if current.is_dir():
                return current
            parent = current.parent
            return parent if parent != current else None
        parent = current.parent
        if parent == current:
            return None
        current = parent


def _dir_is_writable(path: Path) -> bool:
    if path.exists():
        return path.is_dir() and os.access(path, os.W_OK | os.X_OK)

    existing_parent = _nearest_existing_directory(path.parent)
    if existing_parent is None:
        return False
    return os.access(existing_parent, os.W_OK | os.X_OK)


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

    raise RuntimeError(
        f"{label} is not writable at {candidate} and fallback {fallback_path} is also not writable."
    )


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

    raise RuntimeError(
        f"{label} parent is not writable at {candidate.parent} and fallback {fallback_path.parent} is also not writable."
    )


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
    def _warn_if_env_missing(self) -> Settings:
        env_path = BASE_DIR / ".env"
        if not env_path.exists():
            logger.debug(
                ".env no encontrado en %s — usando solo variables de entorno y defaults.",
                env_path,
            )
        return self


def _resolve_user_agent(settings: Settings) -> str:
    """Resolve user-agent from explicit value, fake-useragent, or fallback list."""
    if ua := (settings.user_agent or "").strip():
        return ua

    if settings.enable_fake_ua:
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


def _build_runtime_values(settings: Settings) -> dict[str, Any]:
    data_dir = _resolve_runtime_dir(
        settings.data_dir,
        default=_RUNTIME_DATA_FALLBACK_DIR,
        fallback=_RUNTIME_DATA_FALLBACK_DIR,
        label="DATA_DIR",
    )
    output_dir = _resolve_runtime_dir(
        settings.output_dir,
        default=_RUNTIME_OUTPUT_FALLBACK_DIR,
        fallback=_RUNTIME_OUTPUT_FALLBACK_DIR,
        label="OUTPUT_DIR",
    )
    cookies_file = _resolve_runtime_file(
        settings.cookies_file,
        default=data_dir / "cookies.json",
        fallback_dir=data_dir,
        label="COOKIES_FILE",
    )
    session_db_file = _resolve_runtime_file(
        settings.session_db_file,
        default=data_dir / "session.sqlite3",
        fallback_dir=data_dir,
        label="SESSION_DB_FILE",
    )
    base_url = settings.base_url
    values: dict[str, Any] = {
        "SETTINGS": settings,
        "OUTPUT_DIR": output_dir,
        "DATA_DIR": data_dir,
        "COOKIES_FILE": cookies_file,
        "SESSION_DB_FILE": session_db_file,
        "BASE_URL": base_url,
        "API_V1": f"{base_url}/api/v1",
        "API_V2": f"{base_url}/api/v2",
        "REQUEST_DELAY": settings.request_delay,
        "REQUEST_TIMEOUT": settings.request_timeout,
        "REQUEST_RETRIES": settings.request_retries,
        "REQUEST_RETRY_BACKOFF": settings.request_retry_backoff,
    }
    values["HEADERS"] = MappingProxyType(
        {
            "Accept": settings.accept,
            "Accept-Encoding": settings.accept_encoding,
            "Accept-Language": settings.accept_language,
            "Referer": base_url,
            "User-Agent": _resolve_user_agent(settings),
            **(settings.extra_headers or {}),
        }
    )
    return values


def _ensure_runtime_values() -> dict[str, Any]:
    global _RUNTIME_VALUES
    if _RUNTIME_VALUES is None:
        _RUNTIME_VALUES = _build_runtime_values(Settings())
    return _RUNTIME_VALUES


def _set_runtime_value(name: str, value: Any) -> None:
    values = _ensure_runtime_values()
    settings = values["SETTINGS"]

    if name == "SETTINGS":
        if not isinstance(value, Settings):
            raise TypeError("SETTINGS must be a Settings instance")
        values.clear()
        values.update(_build_runtime_values(value))
        return

    if name == "BASE_URL":
        base_url = str(value).rstrip("/")
        settings.base_url = base_url
        values["BASE_URL"] = base_url
        values["API_V1"] = f"{base_url}/api/v1"
        values["API_V2"] = f"{base_url}/api/v2"
        values["HEADERS"] = MappingProxyType(
            {
                "Accept": settings.accept,
                "Accept-Encoding": settings.accept_encoding,
                "Accept-Language": settings.accept_language,
                "Referer": base_url,
                "User-Agent": _resolve_user_agent(settings),
                **(settings.extra_headers or {}),
            }
        )
        return

    normalized_value = value
    if name == "OUTPUT_DIR":
        normalized_value = Path(value)
        settings.output_dir = normalized_value
    elif name == "DATA_DIR":
        normalized_value = Path(value)
        settings.data_dir = normalized_value
    elif name == "COOKIES_FILE":
        normalized_value = Path(value)
        settings.cookies_file = normalized_value
    elif name == "SESSION_DB_FILE":
        normalized_value = Path(value)
        settings.session_db_file = normalized_value
    elif name == "REQUEST_DELAY":
        normalized_value = float(value)
        settings.request_delay = normalized_value
    elif name == "REQUEST_TIMEOUT":
        normalized_value = int(value)
        settings.request_timeout = normalized_value
    elif name == "REQUEST_RETRIES":
        normalized_value = int(value)
        settings.request_retries = normalized_value
    elif name == "REQUEST_RETRY_BACKOFF":
        normalized_value = float(value)
        settings.request_retry_backoff = normalized_value

    values[name] = normalized_value


def __getattr__(name: str) -> Any:
    if name in _RUNTIME_EXPORTS:
        return _ensure_runtime_values()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_RUNTIME_EXPORTS))


class _ConfigModule(ModuleType):
    """Module wrapper that keeps runtime config lazy and mutable."""

    def __getattr__(self, name: str) -> Any:
        if name in _RUNTIME_EXPORTS:
            return _ensure_runtime_values()[name]
        return super().__getattr__(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in _RUNTIME_EXPORTS:
            _set_runtime_value(name, value)
            return
        super().__setattr__(name, value)


sys.modules[__name__].__class__ = _ConfigModule
