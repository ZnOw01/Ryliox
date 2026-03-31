"""
Mappers para conversión entre entidades de negocio y modelos de persistencia.
Aíslan la lógica de serialización/deserialización.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import sqlite3

from core.dto import (
    DownloadJobDTO,
    DownloadProgressDTO,
    DownloadResultDTO,
    DownloadErrorDTO,
    JobSnapshotDTO,
)


class JSONMapperMixin:
    """Mixin para operaciones JSON comunes."""

    @staticmethod
    def _json_dumps(value: Any) -> str:
        """Serializa valor a JSON compacto."""
        return json.dumps(value, separators=(",", ":"))

    @staticmethod
    def _json_loads(value: str | None) -> Any:
        """Deserializa JSON de forma segura."""
        if value is None:
            return None
        try:
            return json.loads(value)
        except Exception:
            return None


class DownloadJobMapper(JSONMapperMixin):
    """Mapper para DownloadJobDTO <-> SQLite row."""

    def to_db(
        self, dto: DownloadJobDTO, additional_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Convierte DTO a diccionario para inserción en DB."""
        data: dict[str, Any] = {
            "job_id": dto.job_id,
            "book_id": dto.book_id,
            "formats_json": self._json_dumps(dto.formats),
            "chapters_json": self._json_dumps(dto.selected_chapters)
            if dto.selected_chapters is not None
            else None,
            "output_dir": str(dto.output_dir),
            "skip_images": 1 if dto.skip_images else 0,
        }

        if additional_data:
            data.update(additional_data)

        # Timestamps
        now = time.time()
        if "created_at" not in data:
            data["created_at"] = now
        if "updated_at" not in data:
            data["updated_at"] = now

        return data

    def to_dto(self, row: sqlite3.Row | dict[str, Any]) -> DownloadJobDTO:
        """Convierte fila de DB a DTO."""
        formats = self._json_loads(row.get("formats_json"))
        chapters = self._json_loads(row.get("chapters_json"))

        return DownloadJobDTO(
            job_id=str(row["job_id"]),
            book_id=str(row["book_id"]),
            output_dir=Path(str(row["output_dir"])),
            formats=[str(f) for f in formats]
            if isinstance(formats, list)
            else ["epub"],
            selected_chapters=[int(c) for c in chapters]
            if isinstance(chapters, list)
            else None,
            skip_images=bool(row.get("skip_images", 0)),
        )


class DownloadProgressMapper(JSONMapperMixin):
    """Mapper para DownloadProgressDTO <-> SQLite row."""

    def to_db(
        self, dto: DownloadProgressDTO, job_id: str | None = None
    ) -> dict[str, Any]:
        """Convierte DTO a diccionario para actualización en DB."""
        data: dict[str, Any] = {
            "status": dto.status,
            "percentage": dto.percentage,
            "message": dto.message or None,
            "eta_seconds": dto.eta_seconds,
            "current_chapter": dto.current_chapter if dto.current_chapter > 0 else None,
            "total_chapters": dto.total_chapters if dto.total_chapters > 0 else None,
            "chapter_title": dto.chapter_title or None,
            "updated_at": time.time(),
        }

        if job_id:
            data["job_id"] = job_id

        return data

    def to_dto(self, row: sqlite3.Row | dict[str, Any]) -> DownloadProgressDTO:
        """Convierte fila de DB a DTO."""
        return DownloadProgressDTO(
            status=str(row.get("status", "queued")),
            percentage=int(row.get("percentage", 0) or 0),
            message=str(row.get("message", "") or ""),
            eta_seconds=row.get("eta_seconds"),
            current_chapter=int(row.get("current_chapter", 0) or 0),
            total_chapters=int(row.get("total_chapters", 0) or 0),
            chapter_title=str(row.get("chapter_title", "") or ""),
        )


class DownloadResultMapper(JSONMapperMixin):
    """Mapper para DownloadResultDTO <-> SQLite row."""

    def to_db(self, dto: DownloadResultDTO) -> dict[str, Any]:
        """Convierte DTO a diccionario para actualización en DB."""
        pdf_value = dto.pdf_paths
        pdf_json = self._json_dumps(pdf_value) if pdf_value is not None else None

        return {
            "status": "completed",
            "percentage": 100,
            "message": "Completed",
            "title": dto.title,
            "epub": dto.epub_path,
            "pdf_json": pdf_json,
            "error": None,
            "code": None,
            "details_json": None,
            "trace_log": None,
            "cancel_requested": 0,
            "finished_at": time.time(),
            "updated_at": time.time(),
        }

    def to_dto(self, row: sqlite3.Row | dict[str, Any]) -> DownloadResultDTO:
        """Convierte fila de DB a DTO."""
        pdf_value = self._json_loads(row.get("pdf_json"))
        if pdf_value is None and row.get("pdf_json") is not None:
            # Backward compatibility: puede ser un string simple
            pdf_value = row["pdf_json"]

        return DownloadResultDTO(
            book_id=str(row.get("book_id", "")),
            title=str(row.get("title", "")),
            epub_path=row.get("epub"),
            pdf_paths=pdf_value,
            chapters_count=int(row.get("total_chapters", 0) or 0),
        )


class DownloadErrorMapper(JSONMapperMixin):
    """Mapper para DownloadErrorDTO <-> SQLite row."""

    def to_db(self, dto: DownloadErrorDTO) -> dict[str, Any]:
        """Convierte DTO a diccionario para actualización en DB."""
        return {
            "status": dto.code.startswith("cancel") and "cancelled" or "error",
            "error": dto.error,
            "code": dto.code,
            "details_json": self._json_dumps(dto.details) if dto.details else None,
            "trace_log": dto.trace_log,
            "finished_at": time.time(),
            "updated_at": time.time(),
            "message": None,
        }

    def to_dto(self, row: sqlite3.Row | dict[str, Any]) -> DownloadErrorDTO:
        """Convierte fila de DB a DTO."""
        details = self._json_loads(row.get("details_json"))

        return DownloadErrorDTO(
            error=str(row.get("error", "")),
            code=str(row.get("code", "unknown_error")),
            details=details,
            trace_log=row.get("trace_log"),
        )


class JobSnapshotMapper(JSONMapperMixin):
    """Mapper completo para JobSnapshotDTO <-> SQLite row.

    Este mapper combina todos los demás para crear una vista completa del job.
    """

    def __init__(self):
        self.job_mapper = DownloadJobMapper()
        self.progress_mapper = DownloadProgressMapper()
        self.result_mapper = DownloadResultMapper()
        self.error_mapper = DownloadErrorMapper()

    def to_dto(
        self,
        row: sqlite3.Row | dict[str, Any],
        queue_position: int | None = None,
    ) -> JobSnapshotDTO:
        """Convierte fila de DB a snapshot completo."""
        pdf_value = self._json_loads(row.get("pdf_json"))
        if pdf_value is None and row.get("pdf_json") is not None:
            pdf_value = row["pdf_json"]

        details = self._json_loads(row.get("details_json"))

        return JobSnapshotDTO(
            job_id=str(row["job_id"]),
            book_id=str(row["book_id"]),
            status=str(row.get("status", "queued")),
            percentage=int(row.get("percentage", 0) or 0),
            message=str(row.get("message", "") or ""),
            eta_seconds=row.get("eta_seconds"),
            current_chapter=int(row.get("current_chapter", 0) or 0),
            total_chapters=int(row.get("total_chapters", 0) or 0),
            chapter_title=str(row.get("chapter_title", "") or ""),
            title=row.get("title"),
            epub=row.get("epub"),
            pdf=pdf_value,
            error=row.get("error"),
            code=row.get("code"),
            details=details,
            trace_log=row.get("trace_log"),
            queue_position=queue_position,
        )

    def to_dict(
        self,
        row: sqlite3.Row | dict[str, Any],
        queue_position: int | None = None,
    ) -> dict[str, Any]:
        """Convierte fila de DB directamente a diccionario (API response)."""
        snapshot = self.to_dto(row, queue_position)
        return snapshot.to_dict()


# Factory para obtener mappers configurados
def get_mappers() -> dict[str, Any]:
    """Retorna diccionario con todas las instancias de mappers."""
    return {
        "job": DownloadJobMapper(),
        "progress": DownloadProgressMapper(),
        "result": DownloadResultMapper(),
        "error": DownloadErrorMapper(),
        "snapshot": JobSnapshotMapper(),
    }
