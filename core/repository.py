"""Repository pattern for SQLite with Unit of Work."""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager, suppress
from functools import wraps
from pathlib import Path
from typing import Any, Literal, TypeVar

from core.dto import (
    DownloadErrorDTO,
    DownloadJobDTO,
    DownloadProgressDTO,
    DownloadResultDTO,
)
from core.mappers import (
    DownloadErrorMapper,
    DownloadJobMapper,
    DownloadProgressMapper,
    DownloadResultMapper,
    JobSnapshotMapper,
)

logger = logging.getLogger(__name__)

TERMINAL_STATES = frozenset(["completed", "error", "cancelled"])
DEFAULT_TERMINAL_JOB_RETENTION = 500
SQLITE_CONNECTION_TIMEOUT_SECONDS = 30
SQLITE_BUSY_TIMEOUT_MILLISECONDS = 30000
MAX_RETRIES = 3
RETRY_DELAY_BASE = 0.1

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


def sqlite_retry(max_retries: int = MAX_RETRIES) -> Callable[[F], F]:
    """Decorator for SQLite ops with exponential backoff retry."""

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_error: Exception | None = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as exc:
                    last_error = exc
                    if "database is locked" in str(exc).lower():
                        delay = RETRY_DELAY_BASE * (2**attempt)
                        time.sleep(delay)
                        continue
                    raise
            raise (last_error or sqlite3.OperationalError("Max retries exceeded"))

        return wrapper  # type: ignore[return-value]

    return decorator


_SCHEMA_COLUMNS: dict[str, str] = {
    "job_id": "TEXT",
    "book_id": "TEXT",
    "formats_json": "TEXT",
    "chapters_json": "TEXT",
    "output_dir": "TEXT",
    "skip_images": "INTEGER NOT NULL DEFAULT 0",
    "status": "TEXT DEFAULT 'queued'",
    "percentage": "INTEGER",
    "message": "TEXT",
    "eta_seconds": "INTEGER",
    "current_chapter": "INTEGER",
    "total_chapters": "INTEGER",
    "chapter_title": "TEXT",
    "title": "TEXT",
    "epub": "TEXT",
    "pdf_json": "TEXT",
    "error": "TEXT",
    "code": "TEXT",
    "details_json": "TEXT",
    "trace_log": "TEXT",
    "cancel_requested": "INTEGER NOT NULL DEFAULT 0",
    "created_at": "REAL NOT NULL DEFAULT 0",
    "updated_at": "REAL NOT NULL DEFAULT 0",
    "started_at": "REAL",
    "finished_at": "REAL",
}

ALLOWED_SCHEMA_FIELDS: frozenset[str] = frozenset(_SCHEMA_COLUMNS.keys())

# Whitelist of columns allowed in UPDATE operations (security: prevent SQL injection)
_ALLOWED_UPDATE_COLUMNS: frozenset[str] = frozenset(
    {
        "status",
        "percentage",
        "message",
        "eta_seconds",
        "current_chapter",
        "total_chapters",
        "chapter_title",
        "title",
        "epub",
        "pdf_json",
        "error",
        "code",
        "details_json",
        "trace_log",
        "cancel_requested",
        "updated_at",
        "started_at",
        "finished_at",
    }
)


class UnitOfWork:
    """Unit of Work pattern for atomic transactions."""

    def __init__(self, connection: sqlite3.Connection):
        self._conn = connection
        self._committed = False
        self._active = False

    def __enter__(self) -> UnitOfWork:
        """Enter the database transaction context."""
        self._conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MILLISECONDS}")
        self._conn.execute("BEGIN IMMEDIATE")
        self._active = True
        self._committed = False
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Literal[False]:
        """Exit the database transaction context."""
        if not self._active:
            return False

        if exc_type is None and self._committed:
            pass
        elif exc_type is None:
            self._conn.execute("ROLLBACK")
        else:
            with suppress(Exception):
                self._conn.execute("ROLLBACK")

        self._active = False
        return False

    def commit(self) -> None:
        if self._active:
            self._conn.execute("COMMIT")
            self._committed = True

    def rollback(self) -> None:
        if self._active:
            self._conn.execute("ROLLBACK")
            self._committed = False

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn


class DownloadJobRepository:
    """Repository for DownloadJob CRUD operations."""

    def __init__(
        self,
        db_path: Path,
        terminal_job_retention: int = DEFAULT_TERMINAL_JOB_RETENTION,
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.terminal_job_retention = max(0, int(terminal_job_retention))
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None

        self._job_mapper = DownloadJobMapper()
        self._progress_mapper = DownloadProgressMapper()
        self._result_mapper = DownloadResultMapper()
        self._error_mapper = DownloadErrorMapper()
        self._snapshot_mapper = JobSnapshotMapper()

        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=SQLITE_CONNECTION_TIMEOUT_SECONDS,
                check_same_thread=False,
            )
            conn.row_factory = lambda cur, row: {
                col[0]: row[idx] for idx, col in enumerate(cur.description)
            }
            # HIGH-001: Enable WAL mode and verify it was set
            conn.execute("PRAGMA journal_mode=WAL")
            result = conn.execute("PRAGMA journal_mode").fetchone()
            if result and result.get("journal_mode") != "wal":
                logger.warning(
                    "WAL mode could not be enabled, using journal mode: %s",
                    result.get("journal_mode") if result else "unknown",
                )
            conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MILLISECONDS}")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._conn = conn
        return self._conn

    def unit_of_work(self) -> UnitOfWork:
        return UnitOfWork(self._connect())

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        with self._lock:
            conn = self._connect()
            with UnitOfWork(conn) as uow:
                yield conn
                uow.commit()

    def close(self) -> None:
        with self._lock:
            if self._conn is None:
                return
            with suppress(Exception):
                self._conn.close()
            self._conn = None

    def _initialize(self) -> None:
        with self._lock, self._connect() as conn:
            self._create_table(conn)
            self._migrate_schema(conn)
            self._ensure_indexes(conn)
            self._prune_terminal_jobs_conn(conn)
            conn.commit()

    def _create_table(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS download_jobs (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL UNIQUE,
                book_id TEXT NOT NULL,
                formats_json TEXT NOT NULL,
                chapters_json TEXT,
                output_dir TEXT NOT NULL,
                skip_images INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                percentage INTEGER,
                message TEXT,
                eta_seconds INTEGER,
                current_chapter INTEGER,
                total_chapters INTEGER,
                chapter_title TEXT,
                title TEXT,
                epub TEXT,
                pdf_json TEXT,
                error TEXT,
                code TEXT,
                details_json TEXT,
                trace_log TEXT,
                cancel_requested INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                started_at REAL,
                finished_at REAL
            )
            """
        )

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        import time

        rows = conn.execute("PRAGMA table_info(download_jobs)").fetchall()
        existing_columns = {str(row["name"]) for row in rows}

        for column, definition in _SCHEMA_COLUMNS.items():
            if column in existing_columns:
                continue
            conn.execute(f"ALTER TABLE download_jobs ADD COLUMN {column} {definition}")

        now = time.time()
        conn.execute(
            "UPDATE download_jobs SET created_at = ? WHERE created_at IS NULL OR created_at <= 0",
            (now,),
        )
        conn.execute(
            "UPDATE download_jobs SET updated_at = created_at WHERE updated_at IS NULL OR updated_at <= 0",
        )
        conn.execute(
            "UPDATE download_jobs SET status = 'queued' WHERE status IS NULL OR status = ''",
        )

    def _ensure_indexes(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_download_jobs_status_seq ON download_jobs(status, seq)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_download_jobs_job_id ON download_jobs(job_id)")

    def _prune_terminal_jobs_conn(self, conn: sqlite3.Connection) -> None:
        if self.terminal_job_retention <= 0:
            return

        placeholders = ",".join(["?"] * len(TERMINAL_STATES))
        # nosec: B608 - placeholders are from hardcoded TERMINAL_STATES
        conn.execute(
            f"""DELETE FROM download_jobs
            WHERE seq IN (
                SELECT seq FROM download_jobs
                WHERE status IN ({placeholders})
                ORDER BY seq DESC
                LIMIT -1 OFFSET ?
            )
            """,
            (*tuple(TERMINAL_STATES), self.terminal_job_retention),
        )

    def get_by_id(self, job_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            return self._get_by_id_conn(conn, job_id)

    def _get_by_id_conn(self, conn: sqlite3.Connection, job_id: str) -> dict[str, Any] | None:
        row = conn.execute(
            "SELECT * FROM download_jobs WHERE job_id = ? LIMIT 1",
            (job_id,),
        ).fetchone()

        if row is None:
            return None

        queue_position = None
        if row["status"] == "queued":
            queue_position = self._get_queue_position_conn(conn, row["seq"])

        return self._snapshot_mapper.to_dict(row, queue_position)

    def get_latest(self) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM download_jobs ORDER BY seq DESC LIMIT 1").fetchone()

            if row is None:
                return None

            queue_position = None
            if row["status"] == "queued":
                queue_position = self._get_queue_position_conn(conn, row["seq"])

            return self._snapshot_mapper.to_dict(row, queue_position)

    def get_latest_cancellable(self) -> str | None:
        placeholders = ",".join(["?"] * len(TERMINAL_STATES))

        with self._lock, self._connect() as conn:
            # nosec: B608 - placeholders are from hardcoded TERMINAL_STATES
            row = conn.execute(
                f"""SELECT job_id FROM download_jobs
                WHERE status NOT IN ({placeholders})
                    AND status <> 'queued'
                ORDER BY seq DESC
                LIMIT 1""",
                tuple(TERMINAL_STATES),
            ).fetchone()

            if row is not None:
                return str(row["job_id"])

            # nosec: B608 - placeholders are from hardcoded TERMINAL_STATES
            row = conn.execute(
                f"SELECT job_id FROM download_jobs WHERE status NOT IN ({placeholders}) ORDER BY seq DESC LIMIT 1",
                tuple(TERMINAL_STATES),
            ).fetchone()

            if row is None:
                return None

            return str(row["job_id"])

    def list_all(
        self, limit: int | None = None, status_filter: str | None = None
    ) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            query = "SELECT * FROM download_jobs"
            params: list[Any] = []

            if status_filter:
                query += " WHERE status = ?"
                params.append(status_filter)

            query += " ORDER BY seq DESC"

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            rows = conn.execute(query, params).fetchall()

            results = []
            for row in rows:
                queue_position = None
                if row["status"] == "queued":
                    queue_position = self._get_queue_position_conn(conn, row["seq"])
                results.append(self._snapshot_mapper.to_dict(row, queue_position))

            return results

    @sqlite_retry()
    def save(self, job_dto: DownloadJobDTO) -> dict[str, Any]:
        db_data = self._job_mapper.to_db(job_dto)
        db_data.update(
            {
                "status": "queued",
                "percentage": 0,
                "message": "Queued",
                "cancel_requested": 0,
            }
        )

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                    INSERT INTO download_jobs (
                        job_id, book_id, formats_json, chapters_json, output_dir, skip_images,
                        status, percentage, message, cancel_requested, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                    """,
                (
                    db_data["job_id"],
                    db_data["book_id"],
                    db_data["formats_json"],
                    db_data["chapters_json"],
                    db_data["output_dir"],
                    db_data["skip_images"],
                    db_data["status"],
                    db_data["percentage"],
                    db_data["message"],
                    db_data["created_at"],
                    db_data["updated_at"],
                ),
            )

            snapshot = self._get_by_id_conn(conn, job_dto.job_id)
            conn.commit()
            return snapshot or {
                "job_id": job_dto.job_id,
                "status": "queued",
                "book_id": job_dto.book_id,
                "percentage": 0,
            }

    @sqlite_retry()
    def update(self, job_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        if not updates:
            return self.get_by_id(job_id)

        # Security: whitelist columns to prevent SQL injection
        filtered_updates = {k: v for k, v in updates.items() if k in _ALLOWED_UPDATE_COLUMNS}

        if not filtered_updates:
            return self.get_by_id(job_id)

        if "updated_at" not in filtered_updates:
            filtered_updates["updated_at"] = time.time()

        with self._lock, self._connect() as conn:
            # Use proper SQL identifier quoting for column names
            set_clause = ", ".join(
                [f'"{k.replace(chr(34), chr(34) + chr(34))}" = ?' for k in filtered_updates]
            )
            values = [*filtered_updates.values(), job_id]

            # nosec: B608 - column names are from ALLOWED_UPDATE_COLUMNS whitelist
            cursor = conn.execute(
                f"UPDATE download_jobs SET {set_clause} WHERE job_id = ?",
                values,
            )

            if cursor.rowcount == 0:
                conn.commit()
                return None

            snapshot = self._get_by_id_conn(conn, job_id)
            conn.commit()
            return snapshot

    @sqlite_retry()
    def delete(self, job_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM download_jobs WHERE job_id = ?",
                (job_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    @sqlite_retry()
    def claim_next_queued(self) -> DownloadJobDTO | None:
        with self._lock:
            with self.unit_of_work() as uow:
                conn = uow.connection
                row = conn.execute(
                    """
                    SELECT * FROM download_jobs
                    WHERE status = 'queued'
                    ORDER BY seq ASC
                    LIMIT 1
                    """
                ).fetchone()

                if row is None:
                    uow.commit()
                    return None

                now = time.time()
                cursor = conn.execute(
                    """
                    UPDATE download_jobs
                    SET status = ?, updated_at = ?, started_at = COALESCE(started_at, ?), message = NULL
                    WHERE job_id = ? AND status = 'queued'
                    """,
                    ("starting", now, now, row["job_id"]),
                )

                if cursor.rowcount != 1:
                    uow.rollback()
                    return None

                claimed = conn.execute(
                    "SELECT * FROM download_jobs WHERE job_id = ? LIMIT 1",
                    (row["job_id"],),
                ).fetchone()

                uow.commit()

                if claimed is None:
                    return None

                return self._job_mapper.to_dto(claimed)
        return None

    def is_cancel_requested(self, job_id: str) -> bool:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT cancel_requested FROM download_jobs WHERE job_id = ? LIMIT 1",
                (job_id,),
            ).fetchone()
            return bool(row["cancel_requested"]) if row is not None else False

    @sqlite_retry()
    def request_cancel(self, job_id: str) -> tuple[str, dict[str, Any] | None]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM download_jobs WHERE job_id = ? LIMIT 1",
                (job_id,),
            ).fetchone()

            if row is None:
                return "not_found", None

            current_status = str(row["status"])
            if current_status in TERMINAL_STATES:
                return "already_terminal", self._snapshot_mapper.to_dict(row)

            now = time.time()
            if current_status == "queued":
                conn.execute(
                    """
                        UPDATE download_jobs SET
                            status = 'cancelled',
                            message = 'Cancelled',
                            error = 'Download cancelled by user',
                            code = 'download_cancelled',
                            cancel_requested = 1,
                            finished_at = ?,
                            updated_at = ?
                        WHERE job_id = ?
                        """,
                    (now, now, job_id),
                )
                self._prune_terminal_jobs_conn(conn)
                updated = self._get_by_id_conn(conn, job_id)
                conn.commit()
                return "cancelled", updated

            message = row["message"] if row["message"] else "Cancel requested"
            conn.execute(
                """
                    UPDATE download_jobs
                    SET cancel_requested = 1, message = ?, updated_at = ?
                    WHERE job_id = ?
                    """,
                (message, now, job_id),
            )
            updated = self._get_by_id_conn(conn, job_id)
            conn.commit()
            return "cancel_requested", updated

    @sqlite_retry()
    def requeue_inflight(self) -> None:
        placeholders = ",".join(["?"] * len(TERMINAL_STATES))
        terminal_params = tuple(TERMINAL_STATES)
        now = time.time()

        with self._lock, self._connect() as conn:
            # nosec: B608 - placeholders are from hardcoded TERMINAL_STATES
            conn.execute(
                f"""UPDATE download_jobs SET status = 'cancelled',
                    error = COALESCE(error, 'Download cancelled before restart'),
                    code = COALESCE(code, 'download_cancelled'),
                    message = COALESCE(message, 'Cancelled'),
                    finished_at = COALESCE(finished_at, ?),
                    updated_at = ?
                WHERE status NOT IN ({placeholders}) AND cancel_requested = 1""",
                (now, now, *terminal_params),
            )

            # nosec: B608 - placeholders are from hardcoded TERMINAL_STATES
            conn.execute(
                f"""UPDATE download_jobs SET status = 'queued',
                    percentage = 0,
                    eta_seconds = NULL,
                    current_chapter = NULL,
                    total_chapters = NULL,
                    chapter_title = NULL,
                    message = 'Requeued after restart',
                    started_at = NULL,
                    updated_at = ?,
                    cancel_requested = 0
                WHERE status NOT IN ({placeholders}) AND cancel_requested = 0""",
                (now, *terminal_params),
            )

            self._prune_terminal_jobs_conn(conn)
            conn.commit()

    def prune_terminal(self) -> None:
        with self._lock, self._connect() as conn:
            self._prune_terminal_jobs_conn(conn)
            conn.commit()

    def _get_queue_position_conn(self, conn: sqlite3.Connection, seq: int) -> int:
        row = conn.execute(
            "SELECT COUNT(*) AS queue_position FROM download_jobs WHERE status = 'queued' AND seq <= ?",
            (seq,),
        ).fetchone()
        return int(row["queue_position"]) if row else 1

    @sqlite_retry()
    def update_progress(self, job_id: str, progress_dto: DownloadProgressDTO) -> bool:
        db_data = self._progress_mapper.to_db(progress_dto, job_id)
        db_data["updated_at"] = time.time()

        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """
                    UPDATE download_jobs SET
                        status = ?,
                        percentage = ?,
                        message = ?,
                        eta_seconds = ?,
                        current_chapter = ?,
                        total_chapters = ?,
                        chapter_title = ?,
                        updated_at = ?,
                        error = NULL,
                        code = NULL,
                        details_json = NULL,
                        trace_log = NULL
                    WHERE job_id = ? AND status NOT IN ('completed', 'error', 'cancelled')
                    """,
                (
                    db_data["status"],
                    db_data["percentage"],
                    db_data["message"],
                    db_data["eta_seconds"],
                    db_data["current_chapter"],
                    db_data["total_chapters"],
                    db_data["chapter_title"],
                    db_data["updated_at"],
                    job_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    @sqlite_retry()
    def mark_completed(self, job_id: str, result_dto: DownloadResultDTO) -> bool:
        db_data = self._result_mapper.to_db(result_dto)

        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """
                    UPDATE download_jobs SET
                        status = ?,
                        percentage = ?,
                        message = ?,
                        title = ?,
                        epub = ?,
                        pdf_json = ?,
                        error = NULL,
                        code = NULL,
                        details_json = NULL,
                        trace_log = NULL,
                        cancel_requested = 0,
                        finished_at = ?,
                        updated_at = ?
                    WHERE job_id = ?
                    """,
                (
                    db_data["status"],
                    db_data["percentage"],
                    db_data["message"],
                    db_data["title"],
                    db_data["epub"],
                    db_data["pdf_json"],
                    db_data["finished_at"],
                    db_data["updated_at"],
                    job_id,
                ),
            )
            if cursor.rowcount == 0:
                logger.warning("mark_completed: no rows updated for job_id=%s", job_id)
                conn.commit()
                return False
            self._prune_terminal_jobs_conn(conn)
            conn.commit()
            return True

    @sqlite_retry()
    def mark_failed(
        self,
        job_id: str,
        error_dto: DownloadErrorDTO,
        status: str = "error",
    ) -> bool:
        db_data = self._error_mapper.to_db(error_dto)
        db_data["status"] = status
        db_data["updated_at"] = time.time()
        db_data["finished_at"] = time.time()

        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """
                    UPDATE download_jobs SET
                        status = ?,
                        error = ?,
                        code = ?,
                        details_json = ?,
                        trace_log = ?,
                        finished_at = ?,
                        updated_at = ?,
                        message = NULL
                    WHERE job_id = ?
                    """,
                (
                    db_data["status"],
                    db_data["error"],
                    db_data["code"],
                    db_data["details_json"],
                    db_data["trace_log"],
                    db_data["finished_at"],
                    db_data["updated_at"],
                    job_id,
                ),
            )
            if cursor.rowcount == 0:
                logger.warning("mark_failed: no rows updated for job_id=%s", job_id)
                conn.commit()
                return False
            self._prune_terminal_jobs_conn(conn)
            conn.commit()
            return True

    # Legacy compatibility
    def get_job_snapshot(self, job_id: str) -> dict[str, Any] | None:
        return self.get_by_id(job_id)

    def get_latest_job_snapshot(self) -> dict[str, Any] | None:
        return self.get_latest()

    def get_latest_cancellable_job_id(self) -> str | None:
        return self.get_latest_cancellable()

    def cancel_job(self, job_id: str) -> tuple[str, dict[str, Any] | None]:
        return self.request_cancel(job_id)

    def mark_completed_legacy(self, job_id: str, result: Any) -> None:
        from plugins.downloader import DownloadResult

        if isinstance(result, DownloadResult):
            pdf_value = result.files.get("pdf")
            dto = DownloadResultDTO(
                book_id=result.book_id,
                title=result.title,
                epub_path=result.files.get("epub"),
                pdf_paths=pdf_value,
                chapters_count=result.chapters_count,
            )
        else:
            dto = DownloadResultDTO.from_dict(result)

        self.mark_completed(job_id, dto)

    def mark_failed_legacy(
        self,
        *,
        job_id: str,
        status: str,
        error: str,
        code: str,
        details: dict[str, Any] | None = None,
        trace_log: str | None = None,
    ) -> None:
        dto = DownloadErrorDTO(
            error=error,
            code=code,
            details=details,
            trace_log=trace_log,
        )
        self.mark_failed(job_id, dto, status)
