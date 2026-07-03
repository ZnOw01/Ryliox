"""Immutable audit logging with tamper detection."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any

import config
from core.secrets import get_secret
from core.validators import sanitize_for_logs

logger = logging.getLogger(__name__)

# HIGH-001: Use config.SETTINGS.audit.* instead of hardcoded paths
AUDIT_LOG_DIR: Path = getattr(config.SETTINGS.audit, "log_dir", None) or Path(
    os.getenv("AUDIT_LOG_DIR", "./data/audit")
)
AUDIT_LOG_FILE: Path = getattr(config.SETTINGS.audit, "log_file", None) or Path(
    os.getenv("AUDIT_LOG_FILE", "./data/audit.log")
)
AUDIT_RETENTION_DAYS: int = getattr(
    config.SETTINGS.audit, "retention_days", int(os.getenv("AUDIT_RETENTION_DAYS", "365"))
)
AUDIT_ENABLED: bool = os.getenv("AUDIT_ENABLED", "true").lower() in ("true", "1", "yes")
AUDIT_FSYNC_ENABLED: bool = os.getenv("AUDIT_FSYNC_ENABLED", "true").lower() in (
    "true",
    "1",
    "yes",
)

# Constants
_MIN_PRINTABLE_ASCII: int = 32


def _get_audit_hmac_key() -> bytes:
    """Get or create the HMAC key for audit log integrity."""
    key = get_secret("audit_hmac_key")
    if key is None:
        # Generate and store new key
        key = secrets.token_hex(32)
        from core.secrets import set_secret

        set_secret("audit_hmac_key", key)
    return key.encode() if isinstance(key, str) else key


class AuditEventType(Enum):
    """Types of auditable security events."""

    # Authentication
    AUTH_LOGIN = auto()
    AUTH_LOGOUT = auto()
    AUTH_FAILED = auto()
    AUTH_MFA_ATTEMPT = auto()
    AUTH_MFA_SUCCESS = auto()
    AUTH_MFA_FAILED = auto()
    AUTH_SESSION_CREATED = auto()
    AUTH_SESSION_EXPIRED = auto()
    AUTH_SESSION_REVOKED = auto()

    # Authorization
    ACCESS_DENIED = auto()
    ACCESS_GRANTED = auto()
    PRIVILEGE_ESCALATION = auto()

    # Data access
    DATA_READ = auto()
    DATA_WRITE = auto()
    DATA_DELETE = auto()
    DATA_EXPORT = auto()
    DATA_IMPORT = auto()

    # Configuration
    CONFIG_CHANGED = auto()
    CONFIG_VIEWED = auto()

    # Security
    SECRET_ACCESSED = auto()
    SECRET_ROTATED = auto()
    SECRET_CREATED = auto()
    SECRET_DELETED = auto()

    # System
    SYSTEM_STARTUP = auto()
    SYSTEM_SHUTDOWN = auto()
    BACKUP_CREATED = auto()
    BACKUP_RESTORED = auto()

    # Rate limiting
    RATE_LIMIT_EXCEEDED = auto()
    RATE_LIMIT_TRIGGERED = auto()

    # Error events
    ERROR_VALIDATION = auto()
    ERROR_SECURITY = auto()
    ERROR_INJECTION_ATTEMPT = auto()
    ERROR_SSRF_ATTEMPT = auto()

    # Download events
    DOWNLOAD_STARTED = auto()
    DOWNLOAD_COMPLETED = auto()
    DOWNLOAD_FAILED = auto()
    DOWNLOAD_CANCELLED = auto()


class AuditSeverity(Enum):
    """Severity levels for audit events."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True)
class AuditEntry:
    """Immutable audit log entry with integrity verification."""

    timestamp: datetime
    event_type: str
    severity: str
    request_id: str | None
    user_id: str | None
    source_ip: str | None
    user_agent: str | None
    action: str
    resource: str | None
    details: dict[str, Any] = field(default_factory=dict)
    integrity_hash: str = ""
    entry_id: str = field(default_factory=lambda: secrets.token_hex(16))
    prev_hash: str = ""

    def __post_init__(self) -> None:
        """Calculate integrity hash after initialization using HMAC-SHA256."""
        if not self.integrity_hash:
            hash_data = {
                "timestamp": self.timestamp.isoformat(),
                "event_type": self.event_type,
                "severity": self.severity,
                "request_id": self.request_id,
                "user_id": self.user_id,
                "source_ip": self.source_ip,
                "user_agent": self.user_agent,
                "action": self.action,
                "resource": self.resource,
                "details": self.details,
                "entry_id": self.entry_id,
                "prev_hash": self.prev_hash,
            }
            # HIGH-004: Use HMAC-SHA256 with secret key for integrity
            hash_input = json.dumps(hash_data, sort_keys=True, default=str)
            key = _get_audit_hmac_key()
            calculated_hash = hmac.new(key, hash_input.encode(), hashlib.sha256).hexdigest()[:32]
            object.__setattr__(self, "integrity_hash", calculated_hash)

    def to_dict(self) -> dict[str, Any]:
        """Convert entry to dictionary."""
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "severity": self.severity,
            "request_id": self.request_id,
            "user_id": self.user_id,
            "source_ip": self.source_ip,
            "user_agent": self.user_agent,
            "action": self.action,
            "resource": self.resource,
            "details": self.details,
            "integrity_hash": self.integrity_hash,
            "prev_hash": self.prev_hash,
        }

    def to_json(self) -> str:
        """Convert entry to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class AuditLogger:
    """Thread-safe audit logger with integrity verification."""

    _instance: AuditLogger | None = None
    _lock: threading.Lock = threading.Lock()

    _IPV4_PATTERN = re.compile(
        r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    )
    _IPV6_PATTERN = re.compile(
        r"^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$|"
        r"^(?:[0-9a-fA-F]{1,4}:)*::(?:[0-9a-fA-F]{1,4}:)*[0-9a-fA-F]{1,4}$|"
        r"^(?:[0-9a-fA-F]{1,4}:){1,6}::$|"
        r"^(?:[0-9a-fA-F]{1,4}:){1,7}:$"
    )

    @classmethod
    def _reset(cls) -> None:
        """Reset the singleton instance. FOR TESTING ONLY."""
        with cls._lock:
            cls._instance = None

    def __new__(cls, *_args: Any, **_kwargs: Any) -> AuditLogger:
        """Create singleton instance.

        The constructor kwargs (``log_file``, ``retention_days``, ``enabled``) are
        accepted so callers can pass them naturally; they are consumed by
        :meth:`__init__` on the first instantiation and ignored thereafter.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        log_file: Path | None = None,
        retention_days: int = AUDIT_RETENTION_DAYS,
        enabled: bool = AUDIT_ENABLED,
    ) -> None:
        if hasattr(self, "_initialized"):
            return

        self._log_file = log_file or AUDIT_LOG_FILE
        self._retention_days = retention_days
        self._enabled = enabled
        self._last_hash: str = ""
        self._entry_count: int = 0
        self._file_lock: threading.Lock = threading.Lock()
        self._fsync_enabled = AUDIT_FSYNC_ENABLED

        self._log_file.parent.mkdir(parents=True, exist_ok=True)

        self._initialized = True

        self._prune_old_logs()

        if self._enabled:
            self._log_startup()

    def _prune_old_logs(self) -> None:
        """Delete rotated audit log files older than ``retention_days``.

        Rotated logs follow the naming convention ``<log_file_stem>-YYYY-MM-DD.log``
        in the same directory as the active log file. Files whose mtime is older
        than the retention window are removed.
        """
        if self._retention_days <= 0:
            return
        log_dir = self._log_file.parent
        stem = self._log_file.stem
        suffix = self._log_file.suffix
        if not log_dir.exists():
            return
        cutoff = datetime.now(UTC).timestamp() - self._retention_days * 86400
        try:
            for candidate in log_dir.glob(f"{stem}-*{suffix}"):
                try:
                    mtime = candidate.stat().st_mtime
                except OSError:
                    continue
                if mtime < cutoff:
                    try:
                        candidate.unlink()
                    except OSError as exc:
                        logger.warning("Could not delete old audit log %s: %s", candidate, exc)
        except OSError as exc:
            logger.warning("Audit log pruning failed: %s", exc)

    def _validate_ip(self, ip: str | None) -> str | None:
        """Validate and sanitize IP address."""
        if ip is None:
            return None

        sanitized = ip.strip()
        sanitized = "".join(
            c for c in sanitized if ord(c) >= _MIN_PRINTABLE_ASCII and c not in "\r\n"
        )

        if not sanitized:
            return None

        if self._IPV4_PATTERN.match(sanitized) or self._IPV6_PATTERN.match(sanitized):
            return sanitized

        return None

    def _log_startup(self) -> None:
        """Log audit system startup."""
        self.log(
            event_type=AuditEventType.SYSTEM_STARTUP,
            severity=AuditSeverity.INFO,
            action="audit_logger_initialized",
            details={
                "log_file": str(self._log_file),
                "retention_days": self._retention_days,
                "pid": os.getpid(),
            },
        )

    def _write_entry(self, entry: AuditEntry) -> None:
        """Write entry to log file with thread safety and chaining."""
        with self._file_lock:
            try:
                with self._log_file.open("a", encoding="utf-8") as f:
                    f.write(entry.to_json() + "\n")
                    f.flush()
                    if self._fsync_enabled:
                        try:
                            os.fsync(f.fileno())
                        except OSError as exc:
                            logger.warning("Audit log fsync failed: %s", exc)

                self._entry_count += 1
                self._last_hash = entry.integrity_hash
            except OSError:
                logger.exception("Failed to write audit entry")
                raise

    def log(
        self,
        event_type: AuditEventType,
        action: str,
        severity: AuditSeverity = AuditSeverity.INFO,
        request_id: str | None = None,
        user_id: str | None = None,
        source_ip: str | None = None,
        user_agent: str | None = None,
        resource: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEntry | None:
        """Create and log an audit entry."""
        if not self._enabled:
            return None

        safe_details = self._sanitize_details(details or {})
        safe_user_agent = sanitize_for_logs(user_agent, max_length=200) if user_agent else None
        safe_source_ip = self._validate_ip(source_ip)

        entry = AuditEntry(
            timestamp=datetime.now(UTC),
            event_type=event_type.name,
            severity=severity.value,
            request_id=request_id,
            user_id=sanitize_for_logs(user_id, max_length=100) if user_id else None,
            source_ip=safe_source_ip,
            user_agent=safe_user_agent,
            action=action,
            resource=sanitize_for_logs(resource, max_length=500) if resource else None,
            details=safe_details,
            prev_hash=self._last_hash,
        )

        self._write_entry(entry)
        self._mirror_to_logger(entry)

        return entry

    def _sanitize_details(self, details: dict[str, Any]) -> dict[str, Any]:
        """Sanitize sensitive data from audit details."""
        sanitized: dict[str, Any] = {}

        sensitive_keys = {
            "password",
            "token",
            "secret",
            "key",
            "credential",
            "credentials",
            "auth",
            "api_key",
            "apikey",
            "private_key",
            "credit_card",
            "card_number",
            "access_token",
            "refresh_token",
            "session_token",
        }

        for key, value in details.items():
            if key.lower() in sensitive_keys:
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, str):
                sanitized[key] = sanitize_for_logs(value, max_length=1000)
            elif isinstance(value, int | float | bool | type(None)):
                sanitized[key] = value
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_details(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    sanitize_for_logs(str(v), max_length=500) if isinstance(v, str) else v
                    for v in value[:100]
                ]
            else:
                sanitized[key] = sanitize_for_logs(str(value), max_length=500)

        return sanitized

    def _mirror_to_logger(self, entry: AuditEntry) -> None:
        """Mirror audit entry to standard logging."""
        log_method = {
            AuditSeverity.DEBUG.value: logger.debug,
            AuditSeverity.INFO.value: logger.info,
            AuditSeverity.WARNING.value: logger.warning,
            AuditSeverity.ERROR.value: logger.error,
            AuditSeverity.CRITICAL.value: logger.critical,
        }.get(entry.severity, logger.info)

        log_method(
            "AUDIT: %s | %s | %s | req=%s | user=%s | %s",
            entry.event_type,
            entry.severity.upper(),
            entry.action,
            entry.request_id or "-",
            entry.user_id or "-",
            entry.resource or "-",
            extra={
                "audit_entry": entry.to_dict(),
                "event_type": entry.event_type,
                "severity": entry.severity,
            },
        )

    def verify_integrity(self) -> tuple[bool, list[AuditEntry]]:
        """Verify integrity of all log entries."""
        if not self._log_file.exists():
            return True, []

        suspicious = []

        with self._file_lock, self._log_file.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    entry = AuditEntry(
                        timestamp=datetime.fromisoformat(data["timestamp"]),
                        event_type=data["event_type"],
                        severity=data["severity"],
                        request_id=data.get("request_id"),
                        user_id=data.get("user_id"),
                        source_ip=data.get("source_ip"),
                        user_agent=data.get("user_agent"),
                        action=data["action"],
                        resource=data.get("resource"),
                        details=data.get("details", {}),
                        integrity_hash=data.get("integrity_hash", ""),
                        entry_id=data.get("entry_id", ""),
                        prev_hash=data.get("prev_hash", ""),
                    )

                    expected_hash = entry.integrity_hash
                    actual_entry = AuditEntry(
                        timestamp=entry.timestamp,
                        event_type=entry.event_type,
                        severity=entry.severity,
                        request_id=entry.request_id,
                        user_id=entry.user_id,
                        source_ip=entry.source_ip,
                        user_agent=entry.user_agent,
                        action=entry.action,
                        resource=entry.resource,
                        details=entry.details,
                        entry_id=entry.entry_id,
                        prev_hash=entry.prev_hash,
                    )

                    if actual_entry.integrity_hash != expected_hash:
                        suspicious.append(entry)

                except (json.JSONDecodeError, KeyError, ValueError) as exc:
                    logger.error(
                        "Audit log integrity check failed at line %d: %s",
                        line_num,
                        exc,
                    )
                    suspicious.append(_create_corrupt_entry(line_num, exc))

        return len(suspicious) == 0, suspicious

    def search(
        self,
        event_type: AuditEventType | None = None,
        severity: AuditSeverity | None = None,
        request_id: str | None = None,
        user_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Search audit log entries."""
        results: list[AuditEntry] = []

        if not self._log_file.exists():
            return results

        with self._file_lock, self._log_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    entry_time = datetime.fromisoformat(data["timestamp"])

                    if event_type and data["event_type"] != event_type.name:
                        continue
                    if severity and data["severity"] != severity.value:
                        continue
                    if request_id and data.get("request_id") != request_id:
                        continue
                    if user_id and data.get("user_id") != user_id:
                        continue
                    if since and entry_time < since:
                        continue
                    if until and entry_time > until:
                        continue

                    entry = AuditEntry(
                        timestamp=entry_time,
                        event_type=data["event_type"],
                        severity=data["severity"],
                        request_id=data.get("request_id"),
                        user_id=data.get("user_id"),
                        source_ip=data.get("source_ip"),
                        user_agent=data.get("user_agent"),
                        action=data["action"],
                        resource=data.get("resource"),
                        details=data.get("details", {}),
                        integrity_hash=data.get("integrity_hash", ""),
                        entry_id=data.get("entry_id", ""),
                    )

                    results.append(entry)

                    if len(results) >= limit:
                        break

                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

        return results


_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    """Get or initialize the global AuditLogger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def _create_corrupt_entry(line_num: int, exc: Exception) -> AuditEntry:
    """Create a sentinel AuditEntry for corrupt log lines."""
    return AuditEntry(
        timestamp=datetime.now(UTC),
        event_type="CORRUPT_ENTRY",
        severity="CRITICAL",
        request_id=None,
        user_id=None,
        source_ip=None,
        user_agent=None,
        action="integrity_check_failed",
        resource=f"line:{line_num}",
        details={
            "error": str(exc),
            "line_number": line_num,
            "integrity_hash": "CORRUPT",
        },
        integrity_hash="CORRUPT",
    )


def audit_log(
    event_type: AuditEventType,
    action: str,
    severity: AuditSeverity = AuditSeverity.INFO,
    request_id: str | None = None,
    user_id: str | None = None,
    source_ip: str | None = None,
    user_agent: str | None = None,
    resource: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditEntry | None:
    """Convenience function to log an audit entry."""
    return get_audit_logger().log(
        event_type=event_type,
        action=action,
        severity=severity,
        request_id=request_id,
        user_id=user_id,
        source_ip=source_ip,
        user_agent=user_agent,
        resource=resource,
        details=details,
    )


def audit_auth(
    event_type: AuditEventType,
    action: str,
    request_id: str | None = None,
    user_id: str | None = None,
    source_ip: str | None = None,
    success: bool = True,
    details: dict[str, Any] | None = None,
) -> AuditEntry | None:
    """Log authentication-related events."""
    severity = AuditSeverity.INFO if success else AuditSeverity.WARNING
    if event_type in (AuditEventType.AUTH_FAILED, AuditEventType.AUTH_MFA_FAILED):
        severity = AuditSeverity.WARNING

    return audit_log(
        event_type=event_type,
        action=action,
        severity=severity,
        request_id=request_id,
        user_id=user_id,
        source_ip=source_ip,
        details={**(details or {}), "success": success},
    )


def audit_access(
    action: str,
    resource: str,
    granted: bool,
    request_id: str | None = None,
    user_id: str | None = None,
    source_ip: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditEntry | None:
    """Log access control events."""
    event_type = AuditEventType.ACCESS_GRANTED if granted else AuditEventType.ACCESS_DENIED
    severity = AuditSeverity.INFO if granted else AuditSeverity.WARNING

    return audit_log(
        event_type=event_type,
        action=action,
        severity=severity,
        request_id=request_id,
        user_id=user_id,
        source_ip=source_ip,
        resource=resource,
        details={**(details or {}), "granted": granted},
    )


def audit_data(
    event_type: AuditEventType,
    action: str,
    resource: str,
    request_id: str | None = None,
    user_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditEntry | None:
    """Log data access/modification events."""
    return audit_log(
        event_type=event_type,
        action=action,
        request_id=request_id,
        user_id=user_id,
        resource=resource,
        details=details,
    )


def audit_security(
    event_type: AuditEventType,
    action: str,
    request_id: str | None = None,
    source_ip: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditEntry | None:
    """Log security-related events (attacks, violations)."""
    return audit_log(
        event_type=event_type,
        action=action,
        severity=AuditSeverity.ERROR,
        request_id=request_id,
        source_ip=source_ip,
        details=details,
    )


def audit_download(
    event_type: AuditEventType,
    book_id: str,
    job_id: str,
    request_id: str | None = None,
    user_id: str | None = None,
    success: bool = True,
    details: dict[str, Any] | None = None,
) -> AuditEntry | None:
    """Log download-related events."""
    severity = AuditSeverity.INFO if success else AuditSeverity.WARNING
    if event_type == AuditEventType.DOWNLOAD_FAILED:
        severity = AuditSeverity.ERROR

    return audit_log(
        event_type=event_type,
        action=f"download_{event_type.name.split('_')[-1].lower()}",
        severity=severity,
        request_id=request_id,
        user_id=user_id,
        resource=f"book:{book_id},job:{job_id}",
        details={
            **(details or {}),
            "book_id": book_id,
            "job_id": job_id,
            "success": success,
        },
    )


__all__ = [
    "AuditEntry",
    "AuditEventType",
    "AuditLogger",
    "AuditSeverity",
    "audit_access",
    "audit_auth",
    "audit_data",
    "audit_download",
    "audit_log",
    "audit_security",
    "get_audit_logger",
]
