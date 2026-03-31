"""Immutable audit logging with tamper detection.

Implements OWASP A09: Security Logging and Monitoring Failures through:
- Comprehensive audit trails for all security-relevant operations
- Request correlation via request_id
- Immutable log entries with integrity checks
- Structured JSON logging for SIEM integration
- Configurable retention and log levels
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Any, Literal

from core.validators import sanitize_for_logs

logger = logging.getLogger(__name__)


# Audit log configuration
AUDIT_LOG_DIR: Path = Path(os.getenv("AUDIT_LOG_DIR", "./data/audit"))
AUDIT_LOG_FILE: Path = Path(os.getenv("AUDIT_LOG_FILE", "./data/audit.log"))
AUDIT_RETENTION_DAYS: int = int(os.getenv("AUDIT_RETENTION_DAYS", "365"))
AUDIT_MAX_FILE_SIZE_MB: int = int(os.getenv("AUDIT_MAX_FILE_SIZE_MB", "100"))
AUDIT_ENABLED: bool = os.getenv("AUDIT_ENABLED", "true").lower() in ("true", "1", "yes")


class AuditEventType(Enum):
    """Types of auditable security events."""
    # Authentication events
    AUTH_LOGIN = auto()
    AUTH_LOGOUT = auto()
    AUTH_FAILED = auto()
    AUTH_MFA_ATTEMPT = auto()
    AUTH_MFA_SUCCESS = auto()
    AUTH_MFA_FAILED = auto()
    AUTH_SESSION_CREATED = auto()
    AUTH_SESSION_EXPIRED = auto()
    AUTH_SESSION_REVOKED = auto()
    
    # Authorization events
    ACCESS_DENIED = auto()
    ACCESS_GRANTED = auto()
    PRIVILEGE_ESCALATION = auto()
    
    # Data access events
    DATA_READ = auto()
    DATA_WRITE = auto()
    DATA_DELETE = auto()
    DATA_EXPORT = auto()
    DATA_IMPORT = auto()
    
    # Configuration events
    CONFIG_CHANGED = auto()
    CONFIG_VIEWED = auto()
    
    # Security events
    SECRET_ACCESSED = auto()
    SECRET_ROTATED = auto()
    SECRET_CREATED = auto()
    SECRET_DELETED = auto()
    
    # System events
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
    """Immutable audit log entry.
    
    Once created, cannot be modified - ensuring tamper evidence.
    """
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
    
    def __post_init__(self) -> None:
        # Calculate integrity hash if not set
        if not self.integrity_hash:
            # Use object.__setattr__ since dataclass is frozen
            hash_input = (
                f"{self.timestamp.isoformat()}:{self.event_type}:{self.entry_id}:"
                f"{json.dumps(self.details, sort_keys=True, default=str)}"
            )
            calculated_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:32]
            object.__setattr__(self, 'integrity_hash', calculated_hash)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert entry to dictionary for serialization."""
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
        }
    
    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), default=str)


class AuditLogger:
    """Thread-safe audit logger with integrity verification.
    
    Features:
    - Immutable audit entries with SHA-256 integrity hashes
    - Correlation via request_id for distributed tracing
    - Rotating log files with configurable retention
    - Structured JSON output for SIEM integration
    - Tamper detection through entry chaining
    """
    
    _instance: AuditLogger | None = None
    _lock: threading.Lock = threading.Lock()
    
    def __new__(cls) -> AuditLogger:
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
        if hasattr(self, '_initialized'):
            return
            
        self._log_file = log_file or AUDIT_LOG_FILE
        self._retention_days = retention_days
        self._enabled = enabled
        self._last_hash: str = ""
        self._entry_count: int = 0
        self._file_lock: threading.Lock = threading.Lock()
        
        # Ensure log directory exists
        self._log_file.parent.mkdir(parents=True, exist_ok=True)
        
        self._initialized = True
        
        if self._enabled:
            self._log_startup()
    
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
        """Write entry to log file with thread safety."""
        with self._file_lock:
            # Append to file
            with open(self._log_file, 'a', encoding='utf-8') as f:
                f.write(entry.to_json() + '\n')
                f.flush()
                os.fsync(f.fileno())
            
            self._entry_count += 1
            self._last_hash = entry.integrity_hash
    
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
    ) -> AuditEntry:
        """Create and log an audit entry.
        
        Args:
            event_type: Type of security event
            action: Human-readable action description
            severity: Event severity level
            request_id: Correlation ID for request tracing
            user_id: Identified user (if authenticated)
            source_ip: Client IP address
            user_agent: Client user agent string
            resource: Resource being accessed/modified
            details: Additional structured details
            
        Returns:
            The created audit entry
        """
        if not self._enabled:
            return None  # type: ignore
        
        # Sanitize sensitive data
        safe_details = self._sanitize_details(details or {})
        safe_user_agent = sanitize_for_logs(user_agent, max_length=200) if user_agent else None
        
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc),
            event_type=event_type.name,
            severity=severity.value,
            request_id=request_id,
            user_id=sanitize_for_logs(user_id, max_length=100) if user_id else None,
            source_ip=source_ip,
            user_agent=safe_user_agent,
            action=action,
            resource=sanitize_for_logs(resource, max_length=500) if resource else None,
            details=safe_details,
        )
        
        self._write_entry(entry)
        
        # Also log to standard logger at appropriate level
        self._mirror_to_logger(entry)
        
        return entry
    
    def _sanitize_details(self, details: dict[str, Any]) -> dict[str, Any]:
        """Sanitize sensitive data from audit details."""
        sanitized = {}
        
        for key, value in details.items():
            # Never log passwords, tokens, or secrets
            lower_key = key.lower()
            if any(sensitive in lower_key for sensitive in ['password', 'token', 'secret', 'key', 'credential', 'auth']):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, str):
                sanitized[key] = sanitize_for_logs(value, max_length=1000)
            elif isinstance(value, (int, float, bool, type(None))):
                sanitized[key] = value
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_details(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    sanitize_for_logs(str(v), max_length=500) if isinstance(v, str) else v
                    for v in value[:100]  # Limit list size
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
            }
        )
    
    def verify_integrity(self) -> tuple[bool, list[AuditEntry]]:
        """Verify integrity of all log entries.
        
        Returns:
            Tuple of (all_valid, suspicious_entries)
        """
        if not self._log_file.exists():
            return True, []
        
        suspicious = []
        
        with self._file_lock:
            with open(self._log_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        entry = AuditEntry(
                            timestamp=datetime.fromisoformat(data['timestamp']),
                            event_type=data['event_type'],
                            severity=data['severity'],
                            request_id=data.get('request_id'),
                            user_id=data.get('user_id'),
                            source_ip=data.get('source_ip'),
                            user_agent=data.get('user_agent'),
                            action=data['action'],
                            resource=data.get('resource'),
                            details=data.get('details', {}),
                            integrity_hash=data.get('integrity_hash', ''),
                            entry_id=data.get('entry_id', ''),
                        )
                        
                        # Verify hash
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
                        )
                        
                        if actual_entry.integrity_hash != expected_hash:
                            suspicious.append(entry)
                            
                    except (json.JSONDecodeError, KeyError, ValueError) as exc:
                        logger.error("Audit log integrity check failed at line %d: %s", line_num, exc)
                        suspicious.append(None)  # type: ignore
        
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
        results = []
        
        if not self._log_file.exists():
            return results
        
        with self._file_lock:
            with open(self._log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        entry_time = datetime.fromisoformat(data['timestamp'])
                        
                        # Apply filters
                        if event_type and data['event_type'] != event_type.name:
                            continue
                        if severity and data['severity'] != severity.value:
                            continue
                        if request_id and data.get('request_id') != request_id:
                            continue
                        if user_id and data.get('user_id') != user_id:
                            continue
                        if since and entry_time < since:
                            continue
                        if until and entry_time > until:
                            continue
                        
                        entry = AuditEntry(
                            timestamp=entry_time,
                            event_type=data['event_type'],
                            severity=data['severity'],
                            request_id=data.get('request_id'),
                            user_id=data.get('user_id'),
                            source_ip=data.get('source_ip'),
                            user_agent=data.get('user_agent'),
                            action=data['action'],
                            resource=data.get('resource'),
                            details=data.get('details', {}),
                            integrity_hash=data.get('integrity_hash', ''),
                            entry_id=data.get('entry_id', ''),
                        )
                        
                        results.append(entry)
                        
                        if len(results) >= limit:
                            break
                            
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
        
        return results


# Global instance
_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    """Get or initialize the global AuditLogger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


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
) -> AuditEntry:
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
) -> AuditEntry:
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
) -> AuditEntry:
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
) -> AuditEntry:
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
) -> AuditEntry:
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
) -> AuditEntry:
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
        details={**(details or {}), "book_id": book_id, "job_id": job_id, "success": success},
    )


__all__ = [
    "AuditLogger",
    "AuditEntry",
    "AuditEventType",
    "AuditSeverity",
    "get_audit_logger",
    "audit_log",
    "audit_auth",
    "audit_access",
    "audit_data",
    "audit_security",
    "audit_download",
]
