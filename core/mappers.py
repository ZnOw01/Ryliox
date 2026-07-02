"""Mappers for conversion between DTOs and DB models."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core.dto import (
    DownloadErrorDTO,
    DownloadJobDTO,
    DownloadProgressDTO,
    DownloadResultDTO,
    JobSnapshotDTO,
)

logger = logging.getLogger(__name__)

DbRow = Mapping[str, Any]


class JSONMapperMixin:
    """Mixin for JSON operations."""

    @staticmethod
    def _json_dumps(value: Any) -> str:
        """Serialize to compact JSON."""
        return json.dumps(value, separators=(",", ":"))

    @staticmethod
    def _json_loads(value: str | None, context: str = "") -> Any:
        """Deserialize JSON safely with error logging."""
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            logger.warning(
                "JSON decode error%s: %s - input=%r",
                f" ({context})" if context else "",
                exc,
                value[:100] if value else "",
            )
            return None
        except Exception as exc:
            logger.error(
                "Unexpected JSON error%s: %s - input=%r",
                f" ({context})" if context else "",
                exc,
                value[:100] if value else "",
            )
            return None


class DownloadJobMapper(JSONMapperMixin):
    """Mapper for DownloadJobDTO <-> SQLite row."""

    def to_db(
        self, dto: DownloadJobDTO, additional_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Convert DTO to DB dict."""
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

        now = time.time()
        if "created_at" not in data:
            data["created_at"] = now
        if "updated_at" not in data:
            data["updated_at"] = now

        return data

    def to_dto(self, row: DbRow) -> DownloadJobDTO:
        """Convert DB row to DTO."""
        formats = self._json_loads(row.get("formats_json"), "formats_json")
        chapters = self._json_loads(row.get("chapters_json"), "chapters_json")

        return DownloadJobDTO(
            job_id=str(row["job_id"]),
            book_id=str(row["book_id"]),
            output_dir=Path(str(row["output_dir"])),
            formats=[str(f) for f in formats] if isinstance(formats, list) else ["epub"],
            selected_chapters=[int(c) for c in chapters] if isinstance(chapters, list) else None,
            skip_images=bool(row.get("skip_images", 0)),
        )


class DownloadProgressMapper(JSONMapperMixin):
    """Mapper for DownloadProgressDTO <-> SQLite row."""

    def to_db(self, dto: DownloadProgressDTO, job_id: str | None = None) -> dict[str, Any]:
        """Convert DTO to DB dict."""
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

    def to_dto(self, row: DbRow) -> DownloadProgressDTO:
        """Convert DB row to DTO."""
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
    """Mapper for DownloadResultDTO <-> SQLite row."""

    def to_db(self, dto: DownloadResultDTO) -> dict[str, Any]:
        """Convert DTO to DB dict."""
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

    def to_dto(self, row: DbRow) -> DownloadResultDTO:
        """Convert DB row to DTO."""
        pdf_value = self._json_loads(row.get("pdf_json"), "pdf_json")
        if pdf_value is None and row.get("pdf_json") is not None:
            pdf_value = row["pdf_json"]

        return DownloadResultDTO(
            book_id=str(row.get("book_id", "")),
            title=str(row.get("title", "")),
            epub_path=row.get("epub"),
            pdf_paths=pdf_value,
            chapters_count=int(row.get("total_chapters", 0) or 0),
        )


class DownloadErrorMapper(JSONMapperMixin):
    """Mapper for DownloadErrorDTO <-> SQLite row."""

    def to_db(self, dto: DownloadErrorDTO) -> dict[str, Any]:
        """Convert DTO to DB dict."""
        return {
            "status": (dto.code.startswith("cancel") and "cancelled") or "error",
            "error": dto.error,
            "code": dto.code,
            "details_json": self._json_dumps(dto.details) if dto.details else None,
            "trace_log": dto.trace_log,
            "finished_at": time.time(),
            "updated_at": time.time(),
            "message": None,
        }

    def to_dto(self, row: DbRow) -> DownloadErrorDTO:
        """Convert DB row to DTO."""
        details = self._json_loads(row.get("details_json"), "details_json")

        return DownloadErrorDTO(
            error=str(row.get("error", "")),
            code=str(row.get("code", "unknown_error")),
            details=details,
            trace_log=row.get("trace_log"),
        )


class JobSnapshotMapper(JSONMapperMixin):
    """Mapper for JobSnapshotDTO <-> SQLite row."""

    def __init__(self):
        self.job_mapper = DownloadJobMapper()
        self.progress_mapper = DownloadProgressMapper()
        self.result_mapper = DownloadResultMapper()
        self.error_mapper = DownloadErrorMapper()

    def to_dto(
        self,
        row: DbRow,
        queue_position: int | None = None,
    ) -> JobSnapshotDTO:
        """Convert DB row to snapshot DTO."""
        pdf_value = self._json_loads(row.get("pdf_json"), "pdf_json")
        if pdf_value is None and row.get("pdf_json") is not None:
            pdf_value = row["pdf_json"]

        details = self._json_loads(row.get("details_json"), "details_json")

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
        row: DbRow,
        queue_position: int | None = None,
    ) -> dict[str, Any]:
        """Convert DB row directly to dict (API response)."""
        snapshot = self.to_dto(row, queue_position)
        return snapshot.to_dict()


def get_mappers() -> dict[str, Any]:
    """Return dict with all mapper instances."""
    return {
        "job": DownloadJobMapper(),
        "progress": DownloadProgressMapper(),
        "result": DownloadResultMapper(),
        "error": DownloadErrorMapper(),
        "snapshot": JobSnapshotMapper(),
    }
