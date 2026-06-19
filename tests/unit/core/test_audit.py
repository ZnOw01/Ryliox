from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from core.audit import AuditLogger

if TYPE_CHECKING:
    from pathlib import Path


def _reset_audit_logger_singleton() -> None:
    AuditLogger._instance = None


def test_audit_logger_prunes_old_log_files_on_startup(tmp_path: Path) -> None:
    _reset_audit_logger_singleton()

    current_log = tmp_path / "audit.log"
    current_log.write_text("", encoding="utf-8")

    stale_log = tmp_path / "audit-2025-01-01.log"
    stale_log.write_text("stale", encoding="utf-8")

    recent_log = tmp_path / "audit-2026-04-01.log"
    recent_log.write_text("recent", encoding="utf-8")

    stale_age = (datetime.now(UTC) - timedelta(days=10)).timestamp()
    recent_age = (datetime.now(UTC) - timedelta(days=1)).timestamp()

    stale_log.touch()
    recent_log.touch()

    import os

    os.utime(stale_log, (stale_age, stale_age))
    os.utime(recent_log, (recent_age, recent_age))

    AuditLogger(log_file=current_log, retention_days=7, enabled=False)

    assert current_log.exists()
    assert not stale_log.exists()
    assert recent_log.exists()
