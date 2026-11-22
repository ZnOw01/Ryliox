"""Typed configuration for Ryliox.

Every setting can be given as ``RYLIOX_<GROUP>__<FIELD>`` (for example
``RYLIOX_SERVER__PORT=9000``), either in the process environment or in a
``.env`` file in the working directory (``RYLIOX_ENV_FILE`` selects another
file). The short names listed in
``SHORT_NAMES`` are accepted in both places as well; when a setting is given
both ways in the same place, the prefixed spelling wins.

Precedence, highest first: environment, ``.env``, the defaults below.
"""

from __future__ import annotations

import json
import os
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, Field
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    NoDecode,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pydantic.fields import FieldInfo

REPO_ROOT: Path = Path(__file__).resolve().parent
API_V2: str = "/api/v2"

try:
    APP_VERSION: str = metadata.version("ryliox")
except metadata.PackageNotFoundError:  # running from a source tree that was never installed
    APP_VERSION = "0.0.0"


def _split_list(value: object) -> object:
    """Accept ``a,b,c`` as well as a JSON array for list settings."""
    if not isinstance(value, str):
        return value
    text = value.strip()
    if text.startswith("["):
        return json.loads(text)
    return [item.strip() for item in text.split(",") if item.strip()]


StrList = Annotated[list[str], NoDecode, BeforeValidator(_split_list)]


class ServerSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65_535)
    base_url: str = "https://learning.oreilly.com"


class PathSettings(BaseModel):
    """Filesystem locations. Relative paths are resolved against the repository root."""

    output_dir: Path = Path("output")
    # Downloads are confined to this directory. Defaults to ``output_dir``.
    output_root: Path | None = None
    data_dir: Path = Path("data")
    cookies_file: Path | None = None
    session_db_file: Path | None = None


class HttpSettings(BaseModel):
    delay: float = Field(default=0.5, ge=0)
    timeout: int = Field(default=30, ge=1)
    retries: int = Field(default=2, ge=0)
    retry_backoff: float = Field(default=0.5, ge=0)
    request_timeout_seconds: int = 600
    max_redirects: int = 5
    max_response_size_mb: int = 50
    max_assets_per_book: int = 2_000
    user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    accept: str = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    accept_encoding: str = "gzip, deflate"
    accept_language: str = "en-US,en;q=0.5"
    # Sent as ``X-<name>`` so they can never replace a standard header.
    extra_headers: dict[str, str] = Field(default_factory=dict)


class SecuritySettings(BaseModel):
    environment: Literal["development", "production", "test"] = "development"
    enable_security_headers: bool = True
    enable_hsts: bool = False
    hsts_max_age: int = 31_536_000
    allowed_hosts: StrList = Field(default_factory=lambda: ["localhost", "127.0.0.1", "::1"])
    csp_policy: str = (
        "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; "
        "connect-src 'self'; frame-ancestors 'none';"
    )
    max_request_size_mb: int = Field(default=10, ge=1)
    admin_token: str | None = None
    allow_unauthenticated_local_proxy: bool = False
    cors_origins: StrList = Field(
        default_factory=lambda: ["http://localhost:8000", "http://127.0.0.1:8000"]
    )


class RateLimitSettings(BaseModel):
    max_requests: int = 5
    window_seconds: int = 60


class AuditSettings(BaseModel):
    enabled: bool = True
    # Defaults to ``audit.log`` inside the data directory.
    log_file: Path | None = None
    retention_days: int = 365
    fsync_enabled: bool = True
    hmac_key: str | None = None
    hmac_key_file: Path | None = None


class SessionSettings(BaseModel):
    encryption_key: str | None = None
    encryption_key_file: Path | None = None
    old_encryption_keys: StrList = Field(default_factory=list)


class LoggingSettings(BaseModel):
    level: str = "INFO"
    json_logs: bool = False


class MetricsSettings(BaseModel):
    enabled: bool = True


class CacheSettings(BaseModel):
    books_maxsize: int = 256
    books_ttl: int = 3_600
    chapters_maxsize: int = 128
    chapters_ttl: int = 1_800
    search_maxsize: int = 64
    search_ttl: int = 300


class QueueSettings(BaseModel):
    db_name: str = "download_jobs.sqlite3"
    log_dir: str = "logs"
    poll_interval_seconds: float = 0.5
    terminal_job_retention: int = 500
    max_queued_jobs: int = 50
    shutdown_timeout_seconds: float = 10.0


SHORT_NAMES: dict[str, tuple[str, str]] = {
    "HOST": ("server", "host"),
    "PORT": ("server", "port"),
    "BASE_URL": ("server", "base_url"),
    "OUTPUT_DIR": ("paths", "output_dir"),
    "OUTPUT_ROOT": ("paths", "output_root"),
    "DATA_DIR": ("paths", "data_dir"),
    "COOKIES_FILE": ("paths", "cookies_file"),
    "SESSION_DB_FILE": ("paths", "session_db_file"),
    "REQUEST_DELAY": ("http", "delay"),
    "REQUEST_TIMEOUT": ("http", "timeout"),
    "REQUEST_RETRIES": ("http", "retries"),
    "REQUEST_RETRY_BACKOFF": ("http", "retry_backoff"),
    "REQUEST_TIMEOUT_SECONDS": ("http", "request_timeout_seconds"),
    "USER_AGENT": ("http", "user_agent"),
    "ACCEPT": ("http", "accept"),
    "ACCEPT_ENCODING": ("http", "accept_encoding"),
    "ACCEPT_LANGUAGE": ("http", "accept_language"),
    "ENVIRONMENT": ("security", "environment"),
    "ENABLE_SECURITY_HEADERS": ("security", "enable_security_headers"),
    "ENABLE_HSTS": ("security", "enable_hsts"),
    "HSTS_MAX_AGE": ("security", "hsts_max_age"),
    "ALLOWED_HOSTS": ("security", "allowed_hosts"),
    "RYLIOX_TRUSTED_HOSTS": ("security", "allowed_hosts"),
    "CSP_POLICY": ("security", "csp_policy"),
    "MAX_REQUEST_SIZE_MB": ("security", "max_request_size_mb"),
    "ADMIN_TOKEN": ("security", "admin_token"),
    "ALLOW_UNAUTHENTICATED_LOCAL_PROXY": ("security", "allow_unauthenticated_local_proxy"),
    "CORS_ORIGINS": ("security", "cors_origins"),
    "RATE_LIMIT_MAX_REQUESTS": ("rate_limit", "max_requests"),
    "RATE_LIMIT_WINDOW_SECONDS": ("rate_limit", "window_seconds"),
    "AUDIT_ENABLED": ("audit", "enabled"),
    "AUDIT_LOG_FILE": ("audit", "log_file"),
    "AUDIT_RETENTION_DAYS": ("audit", "retention_days"),
    "AUDIT_FSYNC_ENABLED": ("audit", "fsync_enabled"),
    "AUDIT_HMAC_KEY": ("audit", "hmac_key"),
    "SESSION_ENCRYPTION_KEY": ("session", "encryption_key"),
    "LOG_LEVEL": ("logging", "level"),
    "ENABLE_METRICS": ("metrics", "enabled"),
    "CACHE_MAXSIZE_BOOKS": ("cache", "books_maxsize"),
    "CACHE_TTL_BOOKS": ("cache", "books_ttl"),
    "CACHE_MAXSIZE_CHAPTERS": ("cache", "chapters_maxsize"),
    "CACHE_TTL_CHAPTERS": ("cache", "chapters_ttl"),
    "CACHE_MAXSIZE_SEARCH": ("cache", "search_maxsize"),
    "CACHE_TTL_SEARCH": ("cache", "search_ttl"),
}


class _UnprefixedSource(PydanticBaseSettingsSource):
    """Reads the names that do not carry the ``RYLIOX_`` prefix.

    Besides ``SHORT_NAMES`` this keeps the spellings that predate the prefix:
    ``SERVER__PORT=9000`` and ``SERVER='{"port": 9000}'``. A group value is only
    read when it looks like a JSON object, so an unrelated ``SERVER=myhost`` in
    the environment is left alone.
    """

    def __init__(self, settings_cls: type[BaseSettings], values: Mapping[str, str | None]) -> None:
        super().__init__(settings_cls)
        self._values = {name: value for name, value in values.items() if value}

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        groups: dict[str, dict[str, Any]] = {}
        for group in self.settings_cls.model_fields:
            whole = self._values.get(group, "")
            if whole.lstrip().startswith("{"):
                groups[group] = _json_object(group, whole)
            prefix = f"{group}__"
            for name, value in self._values.items():
                if name.startswith(prefix):
                    field = name.removeprefix(prefix)
                    is_object = value.lstrip().startswith("{")
                    groups.setdefault(group, {})[field] = (
                        _json_object(name, value) if is_object else value
                    )
        for name, (group, field) in SHORT_NAMES.items():
            if name.lower() in self._values:
                groups.setdefault(group, {})[field] = self._values[name.lower()]
        return groups


def _json_object(name: str, value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name.upper()} is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{name.upper()} must be a JSON object")
    return parsed


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RYLIOX_",
        env_nested_delimiter="__",
        env_file=os.environ.get("RYLIOX_ENV_FILE", ".env"),
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    server: ServerSettings = Field(default_factory=ServerSettings)
    paths: PathSettings = Field(default_factory=PathSettings)
    http: HttpSettings = Field(default_factory=HttpSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    audit: AuditSettings = Field(default_factory=AuditSettings)
    session: SessionSettings = Field(default_factory=SessionSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    metrics: MetricsSettings = Field(default_factory=MetricsSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    queue: QueueSettings = Field(default_factory=QueueSettings)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        if not isinstance(env_settings, EnvSettingsSource) or not isinstance(
            dotenv_settings, DotEnvSettingsSource
        ):
            raise TypeError("Settings expects the default environment and .env sources")
        # ``env_vars`` holds every variable each source read, with lower-cased names.
        return (
            init_settings,
            env_settings,
            _UnprefixedSource(settings_cls, env_settings.env_vars),
            dotenv_settings,
            _UnprefixedSource(settings_cls, dotenv_settings.env_vars),
        )


def request_headers(http: HttpSettings) -> dict[str, str]:
    return {
        "User-Agent": http.user_agent,
        "Accept": http.accept,
        "Accept-Encoding": http.accept_encoding,
        "Accept-Language": http.accept_language,
        **{f"X-{name}": value for name, value in http.extra_headers.items()},
    }


def _resolve(path: Path) -> Path:
    return (REPO_ROOT / path.expanduser()).resolve()


SETTINGS: Settings = Settings()

BASE_URL: str = SETTINGS.server.base_url
HEADERS: dict[str, str] = request_headers(SETTINGS.http)

DATA_DIR: Path = _resolve(SETTINGS.paths.data_dir)
# Reassigned at runtime by ``POST /api/settings/output-dir``.
OUTPUT_DIR: Path = _resolve(SETTINGS.paths.output_dir)
OUTPUT_ROOT: Path = _resolve(SETTINGS.paths.output_root or SETTINGS.paths.output_dir)
COOKIES_FILE: Path = _resolve(SETTINGS.paths.cookies_file or DATA_DIR / "cookies.json")
SESSION_DB_FILE: Path = _resolve(SETTINGS.paths.session_db_file or DATA_DIR / "session.sqlite3")
DOWNLOAD_QUEUE_DB: Path = DATA_DIR / SETTINGS.queue.db_name
DOWNLOAD_ERROR_LOG_DIR: Path = DATA_DIR / SETTINGS.queue.log_dir
AUDIT_LOG_FILE: Path = _resolve(SETTINGS.audit.log_file or DATA_DIR / "audit.log")
