"""
Patrón Repository para SQLite con Unit of Work.
Abstrae operaciones de base de datos y provee transacciones atómicas.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Generator, TypeVar, Generic

from core.dto import (
    DownloadJobDTO,
    DownloadProgressDTO,
    DownloadResultDTO,
    DownloadErrorDTO,
)
from core.mappers import (
    DownloadJobMapper,
    DownloadProgressMapper,
    DownloadResultMapper,
    DownloadErrorMapper,
    JobSnapshotMapper,
)

# Constants from original implementation
TERMINAL_STATES = frozenset(["completed", "error", "cancelled"])
DEFAULT_TERMINAL_JOB_RETENTION = 500
SQLITE_CONNECTION_TIMEOUT_SECONDS = 30
SQLITE_BUSY_TIMEOUT_MILLISECONDS = 30000

T = TypeVar("T")


class UnitOfWork:
    """
    Implementación del patrón Unit of Work para transacciones atómicas.

    Uso:
        with UnitOfWork(conn) as uow:
            repo.update_job(...)
            repo.save_progress(...)
            uow.commit()  # Todo o nada
    """

    def __init__(self, connection: sqlite3.Connection):
        self._conn = connection
        self._committed = False
        self._active = False

    def __enter__(self) -> UnitOfWork:
        """Inicia la transacción con BEGIN IMMEDIATE para exclusividad."""
        self._conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MILLISECONDS}")
        self._conn.execute("BEGIN IMMEDIATE")
        self._active = True
        self._committed = False
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Finaliza: commit si todo bien, rollback si hay error."""
        if not self._active:
            return False

        if exc_type is None and self._committed:
            # Todo salió bien y se hizo commit explícito
            pass
        elif exc_type is None:
            # No hubo error pero no se hizo commit -> rollback por seguridad
            self._conn.execute("ROLLBACK")
        else:
            # Hubo error -> rollback
            try:
                self._conn.execute("ROLLBACK")
            except Exception:
                pass

        self._active = False
        return False  # No suprimir excepciones

    def commit(self) -> None:
        """Confirma la transacción actual."""
        if self._active:
            self._conn.execute("COMMIT")
            self._committed = True

    def rollback(self) -> None:
        """Deshace la transacción actual."""
        if self._active:
            self._conn.execute("ROLLBACK")
            self._committed = False


class DownloadJobRepository:
    """
    Repository para operaciones CRUD de DownloadJobs.

    Implementa:
    - Patrón Repository para abstraer persistencia
    - Unit of Work para transacciones atómicas
    - Generics para type safety
    - Compatibilidad backward con API existente
    """

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

        # Mappers
        self._job_mapper = DownloadJobMapper()
        self._progress_mapper = DownloadProgressMapper()
        self._result_mapper = DownloadResultMapper()
        self._error_mapper = DownloadErrorMapper()
        self._snapshot_mapper = JobSnapshotMapper()

        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        """Obtiene o crea conexión SQLite con WAL mode."""
        if self._conn is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=SQLITE_CONNECTION_TIMEOUT_SECONDS,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MILLISECONDS}")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._conn = conn
        return self._conn

    def unit_of_work(self) -> UnitOfWork:
        """Factory method para crear un UnitOfWork."""
        return UnitOfWork(self._connect())

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager simplificado para transacciones."""
        with self._lock:
            conn = self._connect()
            with UnitOfWork(conn):
                yield conn

    def close(self) -> None:
        """Cierra la conexión SQLite."""
        with self._lock:
            if self._conn is None:
                return
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def _initialize(self) -> None:
        """Inicializa schema e índices."""
        with self._lock:
            with self._connect() as conn:
                self._create_table(conn)
                self._migrate_schema(conn)
                self._ensure_indexes(conn)
                self._prune_terminal_jobs_conn(conn)
                conn.commit()

    def _create_table(self, conn: sqlite3.Connection) -> None:
        """Crea la tabla principal si no existe."""
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
        """Migra schema añadiendo columnas faltantes."""
        import time

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

    def _ensure_indexes(self, conn: sqlite3.Connection) -> None:
        """Crea índices para queries frecuentes."""
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_download_jobs_status_seq ON download_jobs(status, seq)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_download_jobs_job_id ON download_jobs(job_id)"
        )

    def _prune_terminal_jobs_conn(self, conn: sqlite3.Connection) -> None:
        """Limpia jobs terminales que excedan el límite."""
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

    # === CRUD Operations ===

    def get_by_id(self, job_id: str) -> dict[str, Any] | None:
        """Obtiene un job por su ID."""
        with self._lock:
            with self._connect() as conn:
                return self._get_by_id_conn(conn, job_id)

    def _get_by_id_conn(
        self, conn: sqlite3.Connection, job_id: str
    ) -> dict[str, Any] | None:
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
            return None

        queue_position = None
        if row["status"] == "queued":
            queue_position = self._get_queue_position_conn(conn, row["seq"])

        return self._snapshot_mapper.to_dict(row, queue_position)

    def get_latest(self) -> dict[str, Any] | None:
        """Obtiene el job más reciente por seq."""
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

                if row is None:
                    return None

                queue_position = None
                if row["status"] == "queued":
                    queue_position = self._get_queue_position_conn(conn, row["seq"])

                return self._snapshot_mapper.to_dict(row, queue_position)

    def get_latest_cancellable(self) -> str | None:
        """Obtiene el ID del job más reciente que puede cancelarse."""
        placeholders = ",".join(["?"] * len(TERMINAL_STATES))

        with self._lock:
            with self._connect() as conn:
                # Primero: buscar job activo (no terminal, no queued)
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

                # Segundo: buscar cualquier job no terminal
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

    def list_all(
        self, limit: int | None = None, status_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """Lista jobs con filtros opcionales."""
        with self._lock:
            with self._connect() as conn:
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

    def save(self, job_dto: DownloadJobDTO) -> dict[str, Any]:
        """Guarda un nuevo job y retorna snapshot."""
        db_data = self._job_mapper.to_db(job_dto)
        db_data.update(
            {
                "status": "queued",
                "percentage": 0,
                "message": "Queued",
                "cancel_requested": 0,
            }
        )

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

    def update(self, job_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        """Actualiza campos específicos de un job."""
        if not updates:
            return self.get_by_id(job_id)

        # Filtrar campos permitidos
        allowed_fields = set(self._SCHEMA_COLUMNS.keys()) | {"updated_at"}
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if "updated_at" not in filtered_updates:
            filtered_updates["updated_at"] = time.time()

        with self._lock:
            with self._connect() as conn:
                set_clause = ", ".join([f"{k} = ?" for k in filtered_updates.keys()])
                values = list(filtered_updates.values()) + [job_id]

                cursor = conn.execute(
                    f"""
                    UPDATE download_jobs
                    SET {set_clause}
                    WHERE job_id = ?
                    """,
                    values,
                )

                if cursor.rowcount == 0:
                    conn.commit()
                    return None

                snapshot = self._get_by_id_conn(conn, job_id)
                conn.commit()
                return snapshot

    def delete(self, job_id: str) -> bool:
        """Elimina un job por su ID."""
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    "DELETE FROM download_jobs WHERE job_id = ?",
                    (job_id,),
                )
                conn.commit()
                return cursor.rowcount > 0

    # === Specialized Operations ===

    def claim_next_queued(self) -> DownloadJobDTO | None:
        """
        Reclama el siguiente job en cola (transacción atómica).
        Retorna el DTO del job reclamado o None si no hay jobs.
        """
        with self._lock:
            with self.unit_of_work() as uow:
                row = (
                    self._connect()
                    .execute(
                        """
                    SELECT *
                    FROM download_jobs
                    WHERE status = 'queued'
                    ORDER BY seq ASC
                    LIMIT 1
                    """
                    )
                    .fetchone()
                )

                if row is None:
                    uow.commit()
                    return None

                now = time.time()
                cursor = self._connect().execute(
                    """
                    UPDATE download_jobs
                    SET status = ?, updated_at = ?, started_at = COALESCE(started_at, ?), message = NULL
                    WHERE job_id = ? AND status = 'queued'
                    """,
                    ("starting", now, now, row["job_id"]),
                )

                if cursor.rowcount != 1:
                    uow.commit()
                    return None

                claimed = (
                    self._connect()
                    .execute(
                        """
                    SELECT *
                    FROM download_jobs
                    WHERE job_id = ?
                    LIMIT 1
                    """,
                        (row["job_id"],),
                    )
                    .fetchone()
                )

                uow.commit()

                if claimed is None:
                    return None

                return self._job_mapper.to_dto(claimed)

    def is_cancel_requested(self, job_id: str) -> bool:
        """Verifica si se solicitó cancelación."""
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

    def request_cancel(self, job_id: str) -> tuple[str, dict[str, Any] | None]:
        """
        Solicita cancelación de un job.

        Returns:
            Tuple de (outcome, snapshot):
            - outcome: "not_found", "already_terminal", "cancelled", "cancel_requested"
            - snapshot: estado actual del job o None
        """
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
                    return "already_terminal", self._snapshot_mapper.to_dict(row)

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

    def requeue_inflight(self) -> None:
        """Reencola jobs que quedaron en estado intermedio al reiniciar."""
        placeholders = ",".join(["?"] * len(TERMINAL_STATES))
        terminal_params = tuple(TERMINAL_STATES)
        now = time.time()

        with self._lock:
            with self._connect() as conn:
                # Cancelar jobs que tenían solicitud de cancelación
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

                # Reencolar jobs sin cancelación
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

    def prune_terminal(self) -> None:
        """Limpia jobs terminales que excedan el límite."""
        with self._lock:
            with self._connect() as conn:
                self._prune_terminal_jobs_conn(conn)
                conn.commit()

    def _get_queue_position_conn(self, conn: sqlite3.Connection, seq: int) -> int:
        """Calcula la posición en cola para un job."""
        row = conn.execute(
            """
            SELECT COUNT(*) AS queue_position
            FROM download_jobs
            WHERE status = 'queued' AND seq <= ?
            """,
            (seq,),
        ).fetchone()
        return int(row["queue_position"]) if row else 1

    # === Progress Tracking ===

    def update_progress(self, job_id: str, progress_dto: DownloadProgressDTO) -> bool:
        """Actualiza el progreso de un job."""
        db_data = self._progress_mapper.to_db(progress_dto, job_id)
        db_data["updated_at"] = time.time()

        with self._lock:
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
                return True

    def mark_completed(self, job_id: str, result_dto: DownloadResultDTO) -> None:
        """Marca un job como completado con su resultado."""
        db_data = self._result_mapper.to_db(result_dto)

        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    UPDATE download_jobs
                    SET
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
                self._prune_terminal_jobs_conn(conn)
                conn.commit()

    def mark_failed(
        self,
        job_id: str,
        error_dto: DownloadErrorDTO,
        status: str = "error",
    ) -> None:
        """Marca un job como fallido con información de error."""
        db_data = self._error_mapper.to_db(error_dto)
        db_data["status"] = status
        db_data["updated_at"] = time.time()
        db_data["finished_at"] = time.time()

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
                self._prune_terminal_jobs_conn(conn)
                conn.commit()

    # === Legacy Compatibility ===

    def get_job_snapshot(self, job_id: str) -> dict[str, Any] | None:
        """Alias de compatibilidad hacia atrás para get_by_id."""
        return self.get_by_id(job_id)

    def get_latest_job_snapshot(self) -> dict[str, Any] | None:
        """Alias de compatibilidad hacia atrás para get_latest."""
        return self.get_latest()

    def get_latest_cancellable_job_id(self) -> str | None:
        """Alias de compatibilidad hacia atrás para get_latest_cancellable."""
        return self.get_latest_cancellable()

    def cancel_job(self, job_id: str) -> tuple[str, dict[str, Any] | None]:
        """Alias de compatibilidad hacia atrás para request_cancel."""
        return self.request_cancel(job_id)

    def mark_completed_legacy(self, job_id: str, result: Any) -> None:
        """Compatibilidad con DownloadResult legacy."""
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
        """Compatibilidad con firma legacy de mark_failed."""
        dto = DownloadErrorDTO(
            error=error,
            code=code,
            details=details,
            trace_log=trace_log,
        )
        self.mark_failed(job_id, dto, status)
