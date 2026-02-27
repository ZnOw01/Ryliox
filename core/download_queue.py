"""SQLite-backed download queue and progress persistence."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import time
import traceback
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from core.kernel import Kernel
from plugins.downloader import DownloadProgress, DownloadResult


TERMINAL_STATES = frozenset(["completed", "error", "cancelled"])


@dataclass(frozen=True)
class DownloadJob:
    job_id: str
    book_id: str
    output_dir: Path
    formats: list[str]
    selected_chapters: list[int] | None
    skip_images: bool


class DownloadJobStore:
    """Persists queue, progress, and results for download jobs."""

    _SCHEMA_COLUMNS: dict[str, str] = {
        # SQLite ALTER TABLE ADD COLUMN is limited: avoid UNIQUE/PK constraints here.
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

    def __init__(
        self,
        db_path: Path,
        terminal_job_retention: int = 500,
        progress_write_interval_seconds: float = 0.25,
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.terminal_job_retention = max(0, int(terminal_job_retention))
        self.progress_write_interval_seconds = max(0.0, float(progress_write_interval_seconds))
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        self._last_progress_write_at: dict[str, float] = {}
        self._last_progress_payload: dict[str, tuple[Any, ...]] = {}
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            conn = sqlite3.connect(str(self.db_path), timeout=30, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self._conn = conn
        return self._conn

    def close(self):
        with self._lock:
            if self._conn is None:
                return
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def _initialize(self):
        with self._lock:
            with self._connect() as conn:
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
                self._migrate_schema(conn)
                self._ensure_indexes(conn)
                self._prune_terminal_jobs_conn(conn)
                conn.commit()

    def _migrate_schema(self, conn: sqlite3.Connection):
        rows = conn.execute("PRAGMA table_info(download_jobs)").fetchall()
        existing_columns = {str(row["name"]) for row in rows}

        for column, definition in self._SCHEMA_COLUMNS.items():
            if column in existing_columns:
                continue
            conn.execute(f"ALTER TABLE download_jobs ADD COLUMN {column} {definition}")

        now = time.time()
        conn.execute(
            """
            UPDATE download_jobs
            SET created_at = ?
            WHERE created_at IS NULL OR created_at <= 0
            """,
            (now,),
        )
        conn.execute(
            """
            UPDATE download_jobs
            SET updated_at = created_at
            WHERE updated_at IS NULL OR updated_at <= 0
            """,
        )
        conn.execute(
            """
            UPDATE download_jobs
            SET status = 'queued'
            WHERE status IS NULL OR status = ''
            """,
        )

    def _ensure_indexes(self, conn: sqlite3.Connection):
        conn.execute("CREATE INDEX IF NOT EXISTS idx_download_jobs_status_seq ON download_jobs(status, seq)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_download_jobs_job_id ON download_jobs(job_id)")

    def _prune_terminal_jobs_conn(self, conn: sqlite3.Connection):
        if self.terminal_job_retention <= 0:
            return

        placeholders = ",".join(["?"] * len(TERMINAL_STATES))
        conn.execute(
            f"""
            DELETE FROM download_jobs
            WHERE seq IN (
                SELECT seq
                FROM download_jobs
                WHERE status IN ({placeholders})
                ORDER BY seq DESC
                LIMIT -1 OFFSET ?
            )
            """,
            (*tuple(TERMINAL_STATES), self.terminal_job_retention),
        )

    def _json_dumps(self, value: Any) -> str:
        return json.dumps(value, separators=(",", ":"))

    def _json_loads(self, value: str | None) -> Any:
        if value is None:
            return None
        try:
            return json.loads(value)
        except Exception:
            return None

    def enqueue_job(
        self,
        *,
        book_id: str,
        output_dir: Path,
        formats: list[str],
        selected_chapters: list[int] | None,
        skip_images: bool,
    ) -> dict[str, Any]:
        job_id = uuid.uuid4().hex
        now = time.time()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO download_jobs (
                        job_id, book_id, formats_json, chapters_json, output_dir, skip_images,
                        status, percentage, message, cancel_requested, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                    """,
                    (
                        job_id,
                        str(book_id),
                        self._json_dumps(formats),
                        self._json_dumps(selected_chapters) if selected_chapters is not None else None,
                        str(output_dir),
                        1 if skip_images else 0,
                        "queued",
                        0,
                        "Queued",
                        now,
                        now,
                    ),
                )
                snapshot = self._get_job_snapshot_conn(conn, job_id)
                conn.commit()
                return snapshot or {"job_id": job_id, "status": "queued", "book_id": str(book_id), "percentage": 0}

    def claim_next_queued_job(self) -> DownloadJob | None:
        with self._lock:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    """
                    SELECT *
                    FROM download_jobs
                    WHERE status = 'queued'
                    ORDER BY seq ASC
                    LIMIT 1
                    """
                ).fetchone()
                if row is None:
                    conn.commit()
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
                    conn.commit()
                    return None

                claimed = conn.execute(
                    """
                    SELECT *
                    FROM download_jobs
                    WHERE job_id = ?
                    LIMIT 1
                    """,
                    (row["job_id"],),
                ).fetchone()
                conn.commit()
                if claimed is None:
                    return None
                return self._row_to_job(claimed)

    def requeue_inflight_jobs(self):
        placeholders = ",".join(["?"] * len(TERMINAL_STATES))
        terminal_params = tuple(TERMINAL_STATES)
        now = time.time()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    f"""
                    UPDATE download_jobs
                    SET
                        status = 'cancelled',
                        error = COALESCE(error, 'Download cancelled before restart'),
                        code = COALESCE(code, 'download_cancelled'),
                        message = COALESCE(message, 'Cancelled'),
                        finished_at = COALESCE(finished_at, ?),
                        updated_at = ?
                    WHERE status NOT IN ({placeholders}) AND cancel_requested = 1
                    """,
                    (now, now, *terminal_params),
                )
                conn.execute(
                    f"""
                    UPDATE download_jobs
                    SET
                        status = 'queued',
                        percentage = 0,
                        eta_seconds = NULL,
                        current_chapter = NULL,
                        total_chapters = NULL,
                        chapter_title = NULL,
                        message = 'Requeued after restart',
                        started_at = NULL,
                        updated_at = ?
                    WHERE status NOT IN ({placeholders}) AND cancel_requested = 0
                    """,
                    (now, *terminal_params),
                )
                self._prune_terminal_jobs_conn(conn)
                conn.commit()

    def get_job_snapshot(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            with self._connect() as conn:
                return self._get_job_snapshot_conn(conn, job_id)

    def get_latest_job_snapshot(self) -> dict[str, Any] | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT *
                    FROM download_jobs
                    ORDER BY seq DESC
                    LIMIT 1
                    """
                ).fetchone()
                return self._row_to_snapshot(conn, row) if row is not None else None

    def get_latest_cancellable_job_id(self) -> str | None:
        placeholders = ",".join(["?"] * len(TERMINAL_STATES))
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    f"""
                    SELECT job_id
                    FROM download_jobs
                    WHERE status NOT IN ({placeholders}) AND status <> 'queued'
                    ORDER BY seq DESC
                    LIMIT 1
                    """,
                    tuple(TERMINAL_STATES),
                ).fetchone()
                if row is not None:
                    return str(row["job_id"])
                row = conn.execute(
                    f"""
                    SELECT job_id
                    FROM download_jobs
                    WHERE status NOT IN ({placeholders})
                    ORDER BY seq DESC
                    LIMIT 1
                    """,
                    tuple(TERMINAL_STATES),
                ).fetchone()
                if row is None:
                    return None
                return str(row["job_id"])

    def cancel_job(self, job_id: str) -> tuple[str, dict[str, Any] | None]:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT *
                    FROM download_jobs
                    WHERE job_id = ?
                    LIMIT 1
                    """,
                    (job_id,),
                ).fetchone()
                if row is None:
                    return "not_found", None

                current_status = str(row["status"])
                if current_status in TERMINAL_STATES:
                    return "already_terminal", self._row_to_snapshot(conn, row)

                now = time.time()
                if current_status == "queued":
                    conn.execute(
                        """
                        UPDATE download_jobs
                        SET
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
                    updated = self._get_job_snapshot_conn(conn, job_id)
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
                updated = self._get_job_snapshot_conn(conn, job_id)
                conn.commit()
                return "cancel_requested", updated

    def is_cancel_requested(self, job_id: str) -> bool:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT cancel_requested
                    FROM download_jobs
                    WHERE job_id = ?
                    LIMIT 1
                    """,
                    (job_id,),
                ).fetchone()
                return bool(row["cancel_requested"]) if row is not None else False

    def update_progress(self, job_id: str, progress: DownloadProgress):
        now = time.time()
        current_chapter = (
            int(progress.current_chapter)
            if progress.current_chapter is not None and int(progress.current_chapter) > 0
            else None
        )
        total_chapters = (
            int(progress.total_chapters)
            if progress.total_chapters is not None and int(progress.total_chapters) > 0
            else None
        )
        payload = (
            progress.status,
            int(progress.percentage),
            progress.message or None,
            progress.eta_seconds,
            current_chapter,
            total_chapters,
            progress.chapter_title or None,
        )
        with self._lock:
            previous_payload = self._last_progress_payload.get(job_id)
            previous_at = self._last_progress_write_at.get(job_id, 0.0)
            status_changed = bool(previous_payload and previous_payload[0] != payload[0])
            should_write = (
                previous_payload is None
                or status_changed
                or (now - previous_at) >= self.progress_write_interval_seconds
            )
            if not should_write:
                return
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE download_jobs
                    SET
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
                        progress.status,
                        int(progress.percentage),
                        progress.message or None,
                        progress.eta_seconds,
                        current_chapter,
                        total_chapters,
                        progress.chapter_title or None,
                        now,
                        job_id,
                    ),
                )
                conn.commit()
                self._last_progress_payload[job_id] = payload
                self._last_progress_write_at[job_id] = now

    def mark_completed(self, job_id: str, result: DownloadResult):
        now = time.time()
        pdf_value = result.files.get("pdf")
        pdf_json = self._json_dumps(pdf_value) if pdf_value is not None else None
        epub_value = result.files.get("epub")
        epub_path = str(epub_value) if epub_value is not None else None

        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE download_jobs
                    SET
                        status = 'completed',
                        percentage = 100,
                        message = 'Completed',
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
                    (result.title, epub_path, pdf_json, now, now, job_id),
                )
                self._prune_terminal_jobs_conn(conn)
                conn.commit()
                self._last_progress_payload.pop(job_id, None)
                self._last_progress_write_at.pop(job_id, None)

    def mark_failed(
        self,
        *,
        job_id: str,
        status: str,
        error: str,
        code: str,
        details: dict[str, Any] | None = None,
        trace_log: str | None = None,
    ):
        now = time.time()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE download_jobs
                    SET
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
                        status,
                        error,
                        code,
                        self._json_dumps(details) if details is not None else None,
                        trace_log,
                        now,
                        now,
                        job_id,
                    ),
                )
                self._prune_terminal_jobs_conn(conn)
                conn.commit()
                self._last_progress_payload.pop(job_id, None)
                self._last_progress_write_at.pop(job_id, None)

    def _get_job_snapshot_conn(self, conn: sqlite3.Connection, job_id: str) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT *
            FROM download_jobs
            WHERE job_id = ?
            LIMIT 1
            """,
            (job_id,),
        ).fetchone()
        return self._row_to_snapshot(conn, row) if row is not None else None

    def _row_to_job(self, row: sqlite3.Row) -> DownloadJob:
        formats = self._json_loads(row["formats_json"])
        chapters = self._json_loads(row["chapters_json"])
        return DownloadJob(
            job_id=str(row["job_id"]),
            book_id=str(row["book_id"]),
            output_dir=Path(str(row["output_dir"])),
            formats=[str(item) for item in formats] if isinstance(formats, list) else ["epub"],
            selected_chapters=[int(item) for item in chapters] if isinstance(chapters, list) else None,
            skip_images=bool(row["skip_images"]),
        )

    def _row_to_snapshot(self, conn: sqlite3.Connection, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None

        pdf_value = self._json_loads(row["pdf_json"])
        if pdf_value is None and row["pdf_json"] is not None:
            pdf_value = row["pdf_json"]

        details = self._json_loads(row["details_json"])
        snapshot = {
            "job_id": str(row["job_id"]),
            "status": row["status"],
            "book_id": row["book_id"],
            "percentage": row["percentage"],
            "message": row["message"],
            "eta_seconds": row["eta_seconds"],
            "current_chapter": row["current_chapter"],
            "total_chapters": row["total_chapters"],
            "chapter_title": row["chapter_title"],
            "title": row["title"],
            "epub": row["epub"],
            "pdf": pdf_value,
            "error": row["error"],
            "code": row["code"],
            "details": details,
            "trace_log": row["trace_log"],
        }

        if row["status"] == "queued":
            queue_position_row = conn.execute(
                """
                SELECT COUNT(*) AS queue_position
                FROM download_jobs
                WHERE status = 'queued' AND seq <= ?
                """,
                (row["seq"],),
            ).fetchone()
            snapshot["queue_position"] = int(queue_position_row["queue_position"]) if queue_position_row else 1

        return {key: value for key, value in snapshot.items() if value is not None}


class DownloadQueueService:
    """Worker-backed queue service built on top of DownloadJobStore."""

    def __init__(
        self,
        *,
        kernel_factory: Callable[[], Kernel],
        db_path: Path,
        error_log_dir: Path,
        poll_interval_seconds: float = 0.5,
        terminal_job_retention: int = 500,
    ):
        self.kernel_factory = kernel_factory
        self.store = DownloadJobStore(db_path=db_path, terminal_job_retention=terminal_job_retention)
        self.error_log_dir = Path(error_log_dir)
        self.poll_interval_seconds = max(0.1, float(poll_interval_seconds))
        self._state_lock = threading.Lock()
        self._wake_event = threading.Event()
        self._progress_condition = threading.Condition()
        self._progress_version = 0
        self._stop_event = threading.Event()
        self._active_job_id: str | None = None
        self._active_cancel_event: threading.Event | None = None
        self._worker: threading.Thread | None = None
        self.store.requeue_inflight_jobs()

    def start(self):
        with self._state_lock:
            if self._worker and self._worker.is_alive():
                return
            self._stop_event.clear()
            self._worker = threading.Thread(target=self._worker_loop, name="download-queue-worker", daemon=True)
            self._worker.start()

    def stop(self, timeout_seconds: float = 5.0):
        self._stop_event.set()
        self._wake_event.set()
        self._notify_progress_change()
        worker: threading.Thread | None
        active_cancel_event: threading.Event | None
        with self._state_lock:
            worker = self._worker
            active_cancel_event = self._active_cancel_event
        if active_cancel_event is not None:
            active_cancel_event.set()
        if worker and worker.is_alive():
            worker.join(timeout=max(0.1, timeout_seconds))
        if worker is None or not worker.is_alive():
            self.store.close()

    def enqueue(
        self,
        *,
        book_id: str,
        output_dir: Path,
        formats: list[str],
        selected_chapters: list[int] | None,
        skip_images: bool,
    ) -> dict[str, Any]:
        snapshot = self.store.enqueue_job(
            book_id=book_id,
            output_dir=output_dir,
            formats=formats,
            selected_chapters=selected_chapters,
            skip_images=skip_images,
        )
        self._wake_event.set()
        self._notify_progress_change()
        return snapshot

    def get_progress(self, job_id: str | None = None) -> dict[str, Any]:
        if job_id:
            snapshot = self.store.get_job_snapshot(job_id)
            return snapshot or {}
        latest = self.store.get_latest_job_snapshot()
        return latest or {}

    def cancel(self, job_id: str | None = None) -> tuple[bool, str]:
        target_job_id = job_id or self.store.get_latest_cancellable_job_id()
        if not target_job_id:
            return False, "No active download"

        outcome, snapshot = self.store.cancel_job(target_job_id)
        if outcome == "not_found":
            return False, "Job not found"
        if outcome == "already_terminal":
            return False, "No active download"
        if outcome == "cancelled":
            self._notify_progress_change()
            return True, "Cancel requested"

        with self._state_lock:
            if self._active_job_id == target_job_id and self._active_cancel_event is not None:
                self._active_cancel_event.set()
        self._notify_progress_change()
        return True, "Cancel requested"

    def get_progress_version(self) -> int:
        """Return monotonic progress version for SSE waiters."""
        with self._progress_condition:
            return self._progress_version

    def wait_for_progress_change(self, previous_version: int, timeout_seconds: float) -> int:
        """Block until progress version advances or timeout expires."""
        timeout = max(0.0, float(timeout_seconds))
        with self._progress_condition:
            if self._progress_version != previous_version:
                return self._progress_version
            self._progress_condition.wait(timeout=timeout)
            return self._progress_version

    def _notify_progress_change(self) -> None:
        with self._progress_condition:
            self._progress_version += 1
            self._progress_condition.notify_all()

    def _worker_loop(self):
        while not self._stop_event.is_set():
            job: DownloadJob | None = None
            try:
                job = self.store.claim_next_queued_job()
                if job is None:
                    self._wake_event.wait(self.poll_interval_seconds)
                    self._wake_event.clear()
                    continue
                self._notify_progress_change()
                self._run_job(job)
            except Exception as exc:
                trace_text = traceback.format_exc()
                trace_log = self._write_error_trace(trace_text, (job.job_id if job else "worker"))
                if job is not None:
                    try:
                        self.store.mark_failed(
                            job_id=job.job_id,
                            status="error",
                            error=str(exc) or "Unexpected worker error",
                            code="download_worker_error",
                            details=None,
                            trace_log=trace_log,
                        )
                        self._notify_progress_change()
                    except Exception:
                        pass
                self._wake_event.wait(self.poll_interval_seconds)
                self._wake_event.clear()

    def _run_job(self, job: DownloadJob):
        cancel_event = threading.Event()
        with self._state_lock:
            self._active_job_id = job.job_id
            self._active_cancel_event = cancel_event

        if self.store.is_cancel_requested(job.job_id):
            cancel_event.set()

        try:
            async def run_download() -> DownloadResult:
                kernel = self.kernel_factory()
                downloader = kernel["downloader"]

                def report_progress(progress: DownloadProgress):
                    self.store.update_progress(job.job_id, progress)
                    self._notify_progress_change()

                try:
                    return await downloader.download(
                        book_id=job.book_id,
                        output_dir=job.output_dir,
                        formats=job.formats,
                        selected_chapters=job.selected_chapters,
                        skip_images=job.skip_images,
                        progress_callback=report_progress,
                        cancel_check=lambda: self._is_cancel_requested(job.job_id, cancel_event),
                    )
                finally:
                    try:
                        await kernel.http.close()
                    except Exception:
                        pass

            result = asyncio.run(run_download())
            self.store.mark_completed(job.job_id, result)
            self._notify_progress_change()
        except Exception as exc:
            message = str(exc)
            trace_text = traceback.format_exc()
            trace_log = self._write_error_trace(trace_text, job.job_id)

            if self._is_cancel_requested(job.job_id, cancel_event) or "cancelled" in message.lower():
                error_message = message or "Download cancelled by user"
                self.store.mark_failed(
                    job_id=job.job_id,
                    status="cancelled",
                    error=error_message,
                    code="download_cancelled",
                    details=None,
                    trace_log=trace_log,
                )
                self._notify_progress_change()
            else:
                details = {"trace_log": trace_log} if trace_log else None
                self.store.mark_failed(
                    job_id=job.job_id,
                    status="error",
                    error=message,
                    code="download_failed",
                    details=details,
                    trace_log=trace_log,
                )
                self._notify_progress_change()
        finally:
            with self._state_lock:
                if self._active_job_id == job.job_id:
                    self._active_job_id = None
                    self._active_cancel_event = None
            self._wake_event.set()

    def _is_cancel_requested(self, job_id: str, cancel_event: threading.Event) -> bool:
        if self._stop_event.is_set():
            cancel_event.set()
            return True
        if cancel_event.is_set():
            return True
        if self.store.is_cancel_requested(job_id):
            cancel_event.set()
            return True
        return False

    def _write_error_trace(self, trace_text: str, job_id: str) -> str | None:
        try:
            self.error_log_dir.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time() * 1000)
            log_path = self.error_log_dir / f"download-error-{job_id[:8]}-{timestamp}.log"
            log_path.write_text(trace_text, encoding="utf-8")
            return str(log_path)
        except Exception:
            return None
