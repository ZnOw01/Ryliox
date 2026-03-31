"""
DTOs (Data Transfer Objects) para la capa de aplicación.
Separan la representación de datos de la lógica de negocio y persistencia.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class DownloadJobDTO:
    """DTO inmutable para jobs de descarga.

    Attributes:
        job_id: Identificador único del job
        book_id: ID del libro a descargar
        output_dir: Directorio de salida
        formats: Formatos solicitados (epub, pdf, pdf-chapters)
        selected_chapters: Capítulos seleccionados (None = todos)
        skip_images: Si debe omitir imágenes
    """

    job_id: str
    book_id: str
    output_dir: Path
    formats: list[str] = field(default_factory=lambda: ["epub"])
    selected_chapters: list[int] | None = None
    skip_images: bool = False

    @classmethod
    def create(
        cls,
        book_id: str,
        output_dir: Path,
        formats: list[str] | None = None,
        selected_chapters: list[int] | None = None,
        skip_images: bool = False,
    ) -> "DownloadJobDTO":
        """Factory method con generación automática de job_id."""
        import uuid

        return cls(
            job_id=uuid.uuid4().hex,
            book_id=book_id,
            output_dir=output_dir,
            formats=formats or ["epub"],
            selected_chapters=selected_chapters,
            skip_images=skip_images,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializa a diccionario para persistencia/API."""
        return {
            "job_id": self.job_id,
            "book_id": self.book_id,
            "output_dir": str(self.output_dir),
            "formats": self.formats.copy(),
            "selected_chapters": self.selected_chapters.copy()
            if self.selected_chapters is not None
            else None,
            "skip_images": self.skip_images,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DownloadJobDTO":
        """Deserializa desde diccionario."""
        return cls(
            job_id=str(data["job_id"]),
            book_id=str(data["book_id"]),
            output_dir=Path(str(data.get("output_dir", "."))),
            formats=[str(f) for f in data.get("formats", ["epub"])],
            selected_chapters=[int(i) for i in data["selected_chapters"]]
            if data.get("selected_chapters") is not None
            else None,
            skip_images=bool(data.get("skip_images", False)),
        )


@dataclass(frozen=True, slots=True)
class DownloadProgressDTO:
    """DTO inmutable para el progreso de descarga.

    Attributes:
        status: Estado actual del job
        percentage: Porcentaje de progreso (0-100)
        message: Mensaje descriptivo
        eta_seconds: Tiempo estimado restante
        current_chapter: Capítulo actual siendo procesado
        total_chapters: Total de capítulos
        chapter_title: Título del capítulo actual
        queue_position: Posición en cola (solo para jobs enqueued)
    """

    status: str = "queued"
    percentage: int = 0
    message: str = ""
    eta_seconds: int | None = None
    current_chapter: int = 0
    total_chapters: int = 0
    chapter_title: str = ""
    queue_position: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serializa a diccionario limpio (sin valores None)."""
        data = {
            "status": self.status,
            "percentage": self.percentage,
            "message": self.message,
            "current_chapter": self.current_chapter,
            "total_chapters": self.total_chapters,
            "chapter_title": self.chapter_title,
        }
        if self.eta_seconds is not None:
            data["eta_seconds"] = self.eta_seconds
        if self.queue_position is not None:
            data["queue_position"] = self.queue_position
        return {k: v for k, v in data.items() if v is not None and v != ""}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DownloadProgressDTO":
        """Deserializa desde diccionario."""
        return cls(
            status=str(data.get("status", "queued")),
            percentage=int(data.get("percentage", 0)),
            message=str(data.get("message", "")),
            eta_seconds=data.get("eta_seconds"),
            current_chapter=int(data.get("current_chapter", 0)),
            total_chapters=int(data.get("total_chapters", 0)),
            chapter_title=str(data.get("chapter_title", "")),
            queue_position=data.get("queue_position"),
        )

    def with_updates(self, **kwargs) -> "DownloadProgressDTO":
        """Crea una copia con actualizaciones (patrón inmutable)."""
        current = self.to_dict()
        current.update(kwargs)
        return self.from_dict(current)


@dataclass(frozen=True, slots=True)
class DownloadResultDTO:
    """DTO inmutable para el resultado de descarga completada.

    Attributes:
        book_id: ID del libro descargado
        title: Título del libro
        epub_path: Ruta al archivo EPUB generado
        pdf_paths: Ruta(s) a archivo(s) PDF generado(s)
        chapters_count: Número de capítulos procesados
    """

    book_id: str
    title: str
    epub_path: str | None = None
    pdf_paths: str | list[str] | None = None
    chapters_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serializa a diccionario."""
        result: dict[str, Any] = {
            "book_id": self.book_id,
            "title": self.title,
            "chapters_count": self.chapters_count,
        }
        if self.epub_path is not None:
            result["epub"] = self.epub_path
        if self.pdf_paths is not None:
            result["pdf"] = self.pdf_paths
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DownloadResultDTO":
        """Deserializa desde diccionario."""
        pdf_value = data.get("pdf")
        return cls(
            book_id=str(data.get("book_id", "")),
            title=str(data.get("title", "")),
            epub_path=data.get("epub"),
            pdf_paths=pdf_value,
            chapters_count=int(data.get("chapters_count", 0)),
        )


@dataclass(frozen=True, slots=True)
class DownloadErrorDTO:
    """DTO inmutable para errores de descarga.

    Attributes:
        error: Mensaje de error
        code: Código de error para categorización
        details: Detalles adicionales del error
        trace_log: Ruta al archivo de trace log
    """

    error: str
    code: str = "unknown_error"
    details: dict[str, Any] | None = None
    trace_log: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serializa a diccionario."""
        result: dict[str, Any] = {
            "error": self.error,
            "code": self.code,
        }
        if self.details is not None:
            result["details"] = self.details
        if self.trace_log is not None:
            result["trace_log"] = self.trace_log
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DownloadErrorDTO":
        """Deserializa desde diccionario."""
        return cls(
            error=str(data.get("error", "Unknown error")),
            code=str(data.get("code", "unknown_error")),
            details=data.get("details"),
            trace_log=data.get("trace_log"),
        )


@dataclass(frozen=True, slots=True)
class JobSnapshotDTO:
    """DTO completo para el estado actual de un job (respuesta API).

    Combina DownloadJobDTO + DownloadProgressDTO + resultado/error.
    """

    job_id: str
    book_id: str
    status: str
    percentage: int = 0
    message: str = ""
    eta_seconds: int | None = None
    current_chapter: int = 0
    total_chapters: int = 0
    chapter_title: str = ""
    title: str | None = None
    epub: str | None = None
    pdf: str | list[str] | None = None
    error: str | None = None
    code: str | None = None
    details: dict[str, Any] | None = None
    trace_log: str | None = None
    queue_position: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serializa a diccionario limpio."""
        data: dict[str, Any] = {
            "job_id": self.job_id,
            "book_id": self.book_id,
            "status": self.status,
            "percentage": self.percentage,
        }

        # Solo incluir campos con valores significativos
        if self.message:
            data["message"] = self.message
        if self.eta_seconds is not None:
            data["eta_seconds"] = self.eta_seconds
        if self.current_chapter:
            data["current_chapter"] = self.current_chapter
        if self.total_chapters:
            data["total_chapters"] = self.total_chapters
        if self.chapter_title:
            data["chapter_title"] = self.chapter_title
        if self.title:
            data["title"] = self.title
        if self.epub:
            data["epub"] = self.epub
        if self.pdf:
            data["pdf"] = self.pdf
        if self.error:
            data["error"] = self.error
        if self.code:
            data["code"] = self.code
        if self.details:
            data["details"] = self.details
        if self.trace_log:
            data["trace_log"] = self.trace_log
        if self.queue_position is not None:
            data["queue_position"] = self.queue_position

        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobSnapshotDTO":
        """Deserializa desde diccionario."""
        return cls(
            job_id=str(data["job_id"]),
            book_id=str(data["book_id"]),
            status=str(data.get("status", "queued")),
            percentage=int(data.get("percentage", 0)),
            message=str(data.get("message", "")),
            eta_seconds=data.get("eta_seconds"),
            current_chapter=int(data.get("current_chapter", 0)),
            total_chapters=int(data.get("total_chapters", 0)),
            chapter_title=str(data.get("chapter_title", "")),
            title=data.get("title"),
            epub=data.get("epub"),
            pdf=data.get("pdf"),
            error=data.get("error"),
            code=data.get("code"),
            details=data.get("details"),
            trace_log=data.get("trace_log"),
            queue_position=data.get("queue_position"),
        )
