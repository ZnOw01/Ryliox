"""Centralised configuration for Ryliox.

The ``SETTINGS`` object is an immutable :class:`pydantic_settings.BaseSettings`
loaded from environment variables (or ``.env``). The handful of module-level
constants below are mutable for backward compatibility with the legacy code
that reassigned ``config.OUTPUT_DIR`` at runtime; new code should treat
``SETTINGS`` as the source of truth and avoid mutating these globals.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# ─── Project root ────────────────────────────────────────────────────────────
REPO_ROOT: Path = Path(__file__).resolve().parent


# ─── Pydantic Settings ───────────────────────────────────────────────────────


class ServerSettings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 8000
    base_url: str = "https://learning.oreilly.com"
    app_version: str = "2.0.0"
    astro_fallback_node_version: str = "22.20.0"


class PathSettings(BaseSettings):
    output_dir: Path = Field(default=Path("./output"))
    output_root: Path = Field(default=Path("./output"))
    data_dir: Path = Field(default=Path("./data"))
    cookies_file: Path | None = None
    session_db_file: Path | None = None
    log_dir: str = "logs"
    download_db_name: str = "download_jobs.sqlite3"
    queue_db_name: str = "download_jobs.sqlite3"
    secrets_dir: Path = Field(default=Path("./data/secrets"))
    secrets_file: Path = Field(default=Path("./data/secrets.json.enc"))
    audit_log_dir: Path = Field(default=Path("./data/audit"))
    audit_log_file: Path = Field(default=Path("./data/audit.log"))


class HttpSettings(BaseSettings):
    delay: float = 0.5
    timeout: int = 30
    retries: int = 2
    retry_backoff: float = 0.5
    request_timeout_seconds: int = 600
    max_redirects: int = 5
    max_response_size_mb: int = 50
    max_assets_per_book: int = 2_000
    user_agent: str | None = None
    enable_fake_useragent: bool = False
    accept: str = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    accept_encoding: str = "gzip, deflate"
    accept_language: str = "en-US,en;q=0.5"
    extra_headers: dict[str, str] = Field(default_factory=dict)


class SecuritySettings(BaseSettings):
    environment: Literal["development", "production", "test"] = "development"
    enable_https_redirect: bool = False
    enable_security_headers: bool = True
    enable_hsts: bool = False
    hsts_max_age: int = 31_536_000
    allowed_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1", "::1"])
    csp_policy: str = (
        "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; "
        "connect-src 'self'; frame-ancestors 'none';"
    )
    max_request_size_mb: int = 10
    admin_token: str | None = None
    allow_unauthenticated_local_proxy: bool = False
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:8000", "http://127.0.0.1:8000"]
    )


class RateLimitSettings(BaseSettings):
    max_requests: int = 5
    window_seconds: int = 60
    api_requests: int = 1_000
    api_window: int = 3_600


class SecretsSettings(BaseSettings):
    rotation_days: int = 90
    secrets_dir: Path = Field(default=Path("./data/secrets"))
    secrets_file: Path = Field(default=Path("./data/secrets.json.enc"))


class AuditSettings(BaseSettings):
    enabled: bool = True
    log_dir: Path = Field(default=Path("./data/audit"))
    log_file: Path = Field(default=Path("./data/audit.log"))
    retention_days: int = 365
    hmac_key: str | None = None
    hmac_key_file: Path | None = None


class SessionSettings(BaseSettings):
    cookie_secure: bool = False
    cookie_httponly: bool = True
    cookie_samesite: Literal["Strict", "Lax", "None"] = "Lax"
    max_age: int = 86_400
    encryption_key: str | None = None
    old_encryption_keys: list[str] = Field(default_factory=list)
    encryption_key_file: Path | None = None


class LoggingSettings(BaseSettings):
    level: str = "INFO"
    json_logs: bool = False


class MetricsSettings(BaseSettings):
    enabled: bool = True


class CacheSettings(BaseSettings):
    api_max_age: int = 60
    static_max_age: int = 3_600
    books_maxsize: int = 256
    books_ttl: int = 3_600
    chapters_maxsize: int = 128
    chapters_ttl: int = 1_800
    search_maxsize: int = 64
    search_ttl: int = 300


class QueueSettings(BaseSettings):
    db_name: str = "download_jobs.sqlite3"
    log_dir: str = "logs"
    poll_interval_seconds: float = 0.5
    terminal_job_retention: int = 500
    max_queued_jobs: int = 50
    shutdown_timeout_seconds: float = 10.0


class Settings(BaseSettings):
    """Top-level immutable configuration container.

    Backed by ``.env`` (if present) and process environment variables.
    Nested groups keep the surface area organised without breaking
    backward-compatible flat accessors such as ``settings.csrf_token_length``.
    """

    model_config = SettingsConfigDict(
        env_file=(".env",),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    server: ServerSettings = Field(default_factory=ServerSettings)
    paths: PathSettings = Field(
        default_factory=PathSettings,
        validation_alias=AliasChoices("PATHS", "RYLIOX_PATHS"),
    )
    http: HttpSettings = Field(default_factory=HttpSettings)
    security: SecuritySettings = Field(
        default_factory=SecuritySettings,
        validation_alias=AliasChoices("SECURITY", "RYLIOX_SECURITY"),
    )
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    secrets: SecretsSettings = Field(default_factory=SecretsSettings)
    audit: AuditSettings = Field(
        default_factory=AuditSettings,
        validation_alias=AliasChoices("AUDIT", "RYLIOX_AUDIT"),
    )
    session: SessionSettings = Field(
        default_factory=SessionSettings,
        validation_alias=AliasChoices("SESSION", "RYLIOX_SESSION"),
    )
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    metrics: MetricsSettings = Field(default_factory=MetricsSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    queue: QueueSettings = Field(default_factory=QueueSettings)

    # ── Flat (legacy) accessors used throughout the codebase ──
    csrf_token_length: int = 32
    csrf_token_ttl: int = 3_600
    enable_https_redirect: bool = False
    astro_fallback_node_version: str = "22.20.0"
    download_db_name: str = "download_jobs.sqlite3"
    log_dir: str = "logs"

    def model_post_init(self, __context: Any) -> None:
        # Mirror nested values onto flat legacy fields so old code that
        # calls ``getattr(SETTINGS, "x", default)`` keeps working.
        self.enable_https_redirect = self.security.enable_https_redirect
        self.download_db_name = self.queue.db_name
        self.log_dir = self.queue.log_dir


@lru_cache(maxsize=1)
def _load_settings() -> Settings:
    return Settings()


SETTINGS: Settings = _load_settings()


# ─── Mutable module-level state (legacy compat) ──────────────────────────────
# These mirror the immutable SETTINGS values at import time. A small number of
# routes (e.g. POST /api/settings/output-dir) intentionally reassign them at
# runtime; new code should prefer a settings service instead.


def _resolve(value: Path | str | None, default: str) -> Path:
    if value is None:
        return (REPO_ROOT / default).resolve()
    if isinstance(value, Path):
        return value if value.is_absolute() else (REPO_ROOT / value).resolve()
    return (REPO_ROOT / value).resolve()


OUTPUT_DIR: Path = _resolve(SETTINGS.paths.output_dir, "output")
OUTPUT_ROOT: Path = _resolve(SETTINGS.paths.output_root, "output")
DATA_DIR: Path = _resolve(SETTINGS.paths.data_dir, "data")
COOKIES_FILE: Path = SETTINGS.paths.cookies_file or (DATA_DIR / "cookies.json")
SESSION_DB_FILE: Path = SETTINGS.paths.session_db_file or (DATA_DIR / "session.sqlite3")
DOWNLOAD_QUEUE_DB: Path = DATA_DIR / SETTINGS.queue.db_name
DOWNLOAD_ERROR_LOG_DIR: Path = DATA_DIR / SETTINGS.queue.log_dir

BASE_URL: str = SETTINGS.server.base_url
API_V1: str = "/api/v1"
API_V2: str = "/api/v2"
API_PREFIX: str = "/api"

REQUEST_DELAY: float = SETTINGS.http.delay
REQUEST_TIMEOUT: int = SETTINGS.http.timeout
REQUEST_RETRIES: int = SETTINGS.http.retries
REQUEST_RETRY_BACKOFF: float = SETTINGS.http.retry_backoff
DOWNLOAD_TIMEOUT_SECONDS: int = SETTINGS.http.request_timeout_seconds

HEADERS: dict[str, str] = {
    "User-Agent": SETTINGS.http.user_agent
    or "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": SETTINGS.http.accept,
    "Accept-Encoding": SETTINGS.http.accept_encoding,
    "Accept-Language": SETTINGS.http.accept_language,
    **{f"X-{k}": v for k, v in SETTINGS.http.extra_headers.items()},
}


def reload() -> Settings:
    """Force-reload SETTINGS from the environment (used by tests)."""
    global SETTINGS, OUTPUT_DIR, OUTPUT_ROOT, DATA_DIR, COOKIES_FILE, SESSION_DB_FILE
    global DOWNLOAD_QUEUE_DB, DOWNLOAD_ERROR_LOG_DIR, BASE_URL
    global REQUEST_DELAY, REQUEST_TIMEOUT, REQUEST_RETRIES, REQUEST_RETRY_BACKOFF
    global DOWNLOAD_TIMEOUT_SECONDS, HEADERS
    _load_settings.cache_clear()
    SETTINGS = _load_settings()
    OUTPUT_DIR = _resolve(SETTINGS.paths.output_dir, "output")
    OUTPUT_ROOT = _resolve(SETTINGS.paths.output_root, "output")
    DATA_DIR = _resolve(SETTINGS.paths.data_dir, "data")
    COOKIES_FILE = SETTINGS.paths.cookies_file or (DATA_DIR / "cookies.json")
    SESSION_DB_FILE = SETTINGS.paths.session_db_file or (DATA_DIR / "session.sqlite3")
    DOWNLOAD_QUEUE_DB = DATA_DIR / SETTINGS.queue.db_name
    DOWNLOAD_ERROR_LOG_DIR = DATA_DIR / SETTINGS.queue.log_dir
    BASE_URL = SETTINGS.server.base_url
    REQUEST_DELAY = SETTINGS.http.delay
    REQUEST_TIMEOUT = SETTINGS.http.timeout
    REQUEST_RETRIES = SETTINGS.http.retries
    REQUEST_RETRY_BACKOFF = SETTINGS.http.retry_backoff
    DOWNLOAD_TIMEOUT_SECONDS = SETTINGS.http.request_timeout_seconds
    HEADERS = {
        "User-Agent": SETTINGS.http.user_agent
        or "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": SETTINGS.http.accept,
        "Accept-Encoding": SETTINGS.http.accept_encoding,
        "Accept-Language": SETTINGS.http.accept_language,
        **{f"X-{k}": v for k, v in SETTINGS.http.extra_headers.items()},
    }
    return SETTINGS


__all__ = [
    "SETTINGS",
    "REPO_ROOT",
    "OUTPUT_DIR",
    "OUTPUT_ROOT",
    "DATA_DIR",
    "COOKIES_FILE",
    "SESSION_DB_FILE",
    "DOWNLOAD_QUEUE_DB",
    "DOWNLOAD_ERROR_LOG_DIR",
    "BASE_URL",
    "API_V1",
    "API_V2",
    "API_PREFIX",
    "REQUEST_DELAY",
    "REQUEST_TIMEOUT",
    "REQUEST_RETRIES",
    "REQUEST_RETRY_BACKOFF",
    "DOWNLOAD_TIMEOUT_SECONDS",
    "HEADERS",
    "reload",
    "Settings",
]
