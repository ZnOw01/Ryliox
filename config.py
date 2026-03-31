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
_RUNTIME_OUTPUT_FALLBACK_DIR: Final[Path] = BASE_DIR / "output"

_FALLBACK_USER_AGENTS: Final[tuple[str, ...]] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_6) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
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
    """Convert relative path to absolute path using BASE_DIR."""
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
    """Check if a directory is writable by creating and removing a test file."""
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
    return os.access(existing_parent, os.W_OK | os.X_OK)


def _resolve_runtime_dir(
    configured: Path | None,
    *,
    default: Path,
    fallback: Path,
    label: str,
) -> Path:
    """Resolve runtime directory ensuring it is writable, with fallback."""
    candidate = _to_absolute_path(configured or default)
    if _dir_is_writable(candidate):
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate

    fallback_path = _to_absolute_path(fallback)
    if _dir_is_writable(fallback_path):
        logger.warning(
            "%s is not writable at %s. Using %s.", label, candidate, fallback_path
        )
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
    """Resolve runtime file path ensuring parent directory is writable, with fallback."""
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

    # Security settings
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    enable_https_redirect: bool = Field(
        default=False, validation_alias="ENABLE_HTTPS_REDIRECT"
    )
    enable_security_headers: bool = Field(
        default=True, validation_alias="ENABLE_SECURITY_HEADERS"
    )
    hsts_max_age: int = Field(default=31536000, ge=0, validation_alias="HSTS_MAX_AGE")
    csp_policy: str = Field(
        default=(
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        ),
        validation_alias="CSP_POLICY",
    )
    max_request_size_mb: int = Field(
        default=10, ge=1, validation_alias="MAX_REQUEST_SIZE_MB"
    )
    
    # OWASP Security Hardening
    enable_hsts: bool = Field(default=False, validation_alias="ENABLE_HSTS")
    allowed_hosts: str = Field(
        default="localhost,127.0.0.1,::1", validation_alias="ALLOWED_HOSTS"
    )
    request_timeout_seconds: int = Field(
        default=60, ge=1, validation_alias="REQUEST_TIMEOUT_SECONDS"
    )
    rate_limit_max_requests: int = Field(
        default=100, ge=1, validation_alias="RATE_LIMIT_MAX_REQUESTS"
    )
    rate_limit_window_seconds: int = Field(
        default=60, ge=1, validation_alias="RATE_LIMIT_WINDOW_SECONDS"
    )
    api_rate_limit_requests: int = Field(
        default=1000, ge=1, validation_alias="API_RATE_LIMIT_REQUESTS"
    )
    api_rate_limit_window: int = Field(
        default=3600, ge=1, validation_alias="API_RATE_LIMIT_WINDOW"
    )
    
    # Secret Management
    secret_rotation_days: int = Field(
        default=90, ge=1, validation_alias="SECRET_ROTATION_DAYS"
    )
    secret_master_password: str | None = Field(
        default=None, validation_alias="SECRET_MASTER_PASSWORD"
    )
    secrets_dir: Path | None = Field(default=None, validation_alias="SECRETS_DIR")
    secrets_file: Path | None = Field(default=None, validation_alias="SECRETS_FILE")
    
    # Audit Logging
    audit_enabled: bool = Field(default=True, validation_alias="AUDIT_ENABLED")
    audit_retention_days: int = Field(
        default=365, ge=1, validation_alias="AUDIT_RETENTION_DAYS"
    )
    audit_log_dir: Path | None = Field(default=None, validation_alias="AUDIT_LOG_DIR")
    audit_log_file: Path | None = Field(default=None, validation_alias="AUDIT_LOG_FILE")
    
    # CSRF Protection
    csrf_token_length: int = Field(default=32, ge=16, validation_alias="CSRF_TOKEN_LENGTH")
    csrf_token_ttl: int = Field(default=3600, ge=300, validation_alias="CSRF_TOKEN_TTL")
    
    # Session Security
    session_cookie_secure: bool = Field(
        default=False, validation_alias="SESSION_COOKIE_SECURE"
    )
    session_cookie_httponly: bool = Field(
        default=True, validation_alias="SESSION_COOKIE_HTTPONLY"
    )
    session_cookie_samesite: str = Field(
        default="Lax", validation_alias="SESSION_COOKIE_SAMESITE"
    )
    session_max_age: int = Field(
        default=86400, ge=300, validation_alias="SESSION_MAX_AGE"
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

    @field_validator("base_url")
    @classmethod
    def _validate_url(cls, v: str) -> str:
        """Validate that base_url starts with http:// or https://."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        return v

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
                f"extra_headers cannot override protected headers: {sorted(conflicts)}. "
                "Use USER_AGENT, ACCEPT, ACCEPT_ENCODING, or ACCEPT_LANGUAGE instead."
            )
        return v

    @model_validator(mode="after")
    def _warn_if_env_missing(self) -> Settings:
        env_path = BASE_DIR / ".env"
        if not env_path.exists():
            logger.debug(
                ".env not found at %s — using environment variables and defaults only.",
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
            logger.debug(
                "fake_useragent returned unexpected value (%r), using fallback.",
                candidate,
            )
        except ImportError:
            logger.debug("fake_useragent not installed, using fallback.")
        except Exception as exc:
            logger.debug("fake_useragent unavailable (%s), using fallback.", exc)

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

# Security configuration constants
IS_PRODUCTION: Final[bool] = SETTINGS.environment.lower() in ("production", "prod")
ENABLE_HTTPS_REDIRECT: Final[bool] = SETTINGS.enable_https_redirect
ENABLE_SECURITY_HEADERS: Final[bool] = SETTINGS.enable_security_headers
HSTS_MAX_AGE: Final[int] = SETTINGS.hsts_max_age
CSP_POLICY: Final[str] = SETTINGS.csp_policy
MAX_REQUEST_SIZE_MB: Final[int] = SETTINGS.max_request_size_mb
MAX_REQUEST_SIZE_BYTES: Final[int] = MAX_REQUEST_SIZE_MB * 1024 * 1024
