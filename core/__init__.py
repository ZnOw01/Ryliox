"""Core package exports with lazy imports."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from . import process_manager
    from .http_client import HttpClient
    from .kernel import Kernel, create_default_kernel
    from .types import BookInfo, ChapterInfo, ChapterSummary, FormatInfo

__all__ = [
    "Kernel",
    "create_default_kernel",
    "HttpClient",
    "ChapterInfo",
    "ChapterSummary",
    "BookInfo",
    "FormatInfo",
    "process_manager",
    # New architectural exports (2024 refactor)
    "DownloadJobRepository",
    "DownloadQueueService",
    "UnitOfWork",
    "DownloadJobDTO",
    "DownloadProgressDTO",
    "DownloadResultDTO",
    "DownloadErrorDTO",
    "JobSnapshotDTO",
    # OWASP Security exports (2026)
    "validate_book_id",
    "validate_url",
    "validate_file_path",
    "validate_user_input",
    "ValidationError",
    "SecretManager",
    "generate_secure_token",
    "get_audit_logger",
    "audit_log",
    "AuditEventType",
    "AuditSeverity",
]


def __getattr__(name: str) -> Any:
    if name in {"Kernel", "create_default_kernel"}:
        module = import_module(".kernel", __name__)
        return getattr(module, name)

    if name == "HttpClient":
        module = import_module(".http_client", __name__)
        return module.HttpClient

    if name in {"ChapterInfo", "ChapterSummary", "BookInfo", "FormatInfo"}:
        module = import_module(".types", __name__)
        return getattr(module, name)

    if name == "process_manager":
        return import_module(".process_manager", __name__)

    # New architectural classes (2024 refactor)
    if name == "DownloadJobRepository":
        module = import_module(".repository", __name__)
        return module.DownloadJobRepository

    if name == "UnitOfWork":
        module = import_module(".repository", __name__)
        return module.UnitOfWork

    if name == "DownloadQueueService":
        module = import_module(".services", __name__)
        return module.DownloadQueueService

    if name in {
        "DownloadJobDTO",
        "DownloadProgressDTO",
        "DownloadResultDTO",
        "DownloadErrorDTO",
        "JobSnapshotDTO",
    }:
        module = import_module(".dto", __name__)
        return getattr(module, name)

    # OWASP Security modules (2026)
    if name in {
        "validate_book_id",
        "validate_url",
        "validate_file_path",
        "validate_user_input",
        "ValidationError",
    }:
        module = import_module(".validators", __name__)
        return getattr(module, name)

    if name in {"SecretManager", "generate_secure_token"}:
        module = import_module(".secrets", __name__)
        return getattr(module, name)

    if name in {"get_audit_logger", "audit_log", "AuditEventType", "AuditSeverity"}:
        module = import_module(".audit", __name__)
        return getattr(module, name)

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
