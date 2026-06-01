"""DTOs (Data Transfer Objects) for the application layer using Pydantic."""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DownloadJobDTO(BaseModel):
    """DTO for download jobs."""

    model_config = ConfigDict(frozen=True, slots=True)

    job_id: str = Field(default_factory=lambda: secrets.token_hex(16))
    book_id: str
    output_dir: Path
    formats: list[str] = Field(default_factory=lambda: ["epub"])
    selected_chapters: list[int] | None = None
    skip_images: bool = False

    @field_validator("output_dir", mode="before")
    @classmethod
    def _validate_output_dir(cls, v: str | Path) -> Path:
        """Ensure output_dir is a Path object."""
        if isinstance(v, str):
            return Path(v)
        return v

    def model_dump(self, **kwargs) -> dict[str, Any]:
        """Custom serialization for JSON compatibility."""
        data = super().model_dump(**kwargs)
        data["output_dir"] = str(self.output_dir)
        if self.selected_chapters is not None:
            data["selected_chapters"] = list(self.selected_chapters)
        return data

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> DownloadJobDTO:
        """Custom deserialization from dict."""
        processed = dict(data)
        processed["job_id"] = str(data.get("job_id", secrets.token_hex(16)))
        processed["book_id"] = str(data["book_id"])
        processed["output_dir"] = Path(str(data.get("output_dir", ".")))
        processed["formats"] = [str(f) for f in data.get("formats", ["epub"])]
        if data.get("selected_chapters") is not None:
            processed["selected_chapters"] = [int(i) for i in data["selected_chapters"]]
        processed["skip_images"] = bool(data.get("skip_images", False))
        return super().model_validate(processed)

    @classmethod
    def create(
        cls,
        book_id: str,
        output_dir: Path,
        formats: list[str] | None = None,
        selected_chapters: list[int] | None = None,
        skip_images: bool = False,
    ) -> DownloadJobDTO:
        """Factory method with auto-generated job_id."""
        return cls(
            job_id=secrets.token_hex(16),
            book_id=book_id,
            output_dir=output_dir,
            formats=formats or ["epub"],
            selected_chapters=selected_chapters,
            skip_images=skip_images,
        )

    # Backward compatibility aliases
    def to_dict(self) -> dict[str, Any]:
        """Deprecated: Use model_dump() instead."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DownloadJobDTO:
        """Deprecated: Use model_validate() instead."""
        return cls.model_validate(data)


class DownloadProgressDTO(BaseModel):
    """DTO for download progress."""

    model_config = ConfigDict(frozen=True, slots=True)

    status: str = "queued"
    percentage: int = 0
    message: str = ""
    eta_seconds: int | None = None
    current_chapter: int = 0
    total_chapters: int = 0
    chapter_title: str = ""
    queue_position: int | None = None

    def model_dump(self, **kwargs) -> dict[str, Any]:
        """Custom serialization - only include non-null values."""
        data: dict[str, Any] = {
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
        # Filter out empty strings and None values for cleaner JSON
        return {k: v for k, v in data.items() if v is not None and v != ""}

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> DownloadProgressDTO:
        """Custom deserialization from dict."""
        processed = {
            "status": str(data.get("status", "queued")),
            "percentage": int(data.get("percentage", 0)),
            "message": str(data.get("message", "")),
            "eta_seconds": data.get("eta_seconds"),
            "current_chapter": int(data.get("current_chapter", 0)),
            "total_chapters": int(data.get("total_chapters", 0)),
            "chapter_title": str(data.get("chapter_title", "")),
            "queue_position": data.get("queue_position"),
        }
        return super().model_validate(processed)

    def with_updates(self, **kwargs) -> DownloadProgressDTO:
        """Create a copy with updates (immutable pattern)."""
        current = self.model_dump()
        current.update(kwargs)
        return self.model_validate(current)

    # Backward compatibility aliases
    def to_dict(self) -> dict[str, Any]:
        """Deprecated: Use model_dump() instead."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DownloadProgressDTO:
        """Deprecated: Use model_validate() instead."""
        return cls.model_validate(data)


class DownloadResultDTO(BaseModel):
    """DTO for completed download result."""

    model_config = ConfigDict(frozen=True, slots=True)

    book_id: str
    title: str
    epub_path: str | None = None
    pdf_paths: str | list[str] | None = None
    chapters_count: int = 0

    def model_dump(self, **kwargs) -> dict[str, Any]:
        """Custom serialization - conditionally include optional fields."""
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
    def model_validate(cls, data: dict[str, Any]) -> DownloadResultDTO:
        """Custom deserialization from dict."""
        pdf_value = data.get("pdf")
        processed = {
            "book_id": str(data.get("book_id", "")),
            "title": str(data.get("title", "")),
            "epub_path": data.get("epub"),
            "pdf_paths": pdf_value,
            "chapters_count": int(data.get("chapters_count", 0)),
        }
        return super().model_validate(processed)

    # Backward compatibility aliases
    def to_dict(self) -> dict[str, Any]:
        """Deprecated: Use model_dump() instead."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DownloadResultDTO:
        """Deprecated: Use model_validate() instead."""
        return cls.model_validate(data)


class DownloadErrorDTO(BaseModel):
    """DTO for download errors."""

    model_config = ConfigDict(frozen=True, slots=True)

    error: str
    code: str = "unknown_error"
    details: dict[str, Any] | None = None
    trace_log: str | None = None

    def model_dump(self, **kwargs) -> dict[str, Any]:
        """Custom serialization - conditionally include optional fields."""
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
    def model_validate(cls, data: dict[str, Any]) -> DownloadErrorDTO:
        """Custom deserialization from dict."""
        processed = {
            "error": str(data.get("error", "Unknown error")),
            "code": str(data.get("code", "unknown_error")),
            "details": data.get("details"),
            "trace_log": data.get("trace_log"),
        }
        return super().model_validate(processed)

    # Backward compatibility aliases
    def to_dict(self) -> dict[str, Any]:
        """Deprecated: Use model_dump() instead."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DownloadErrorDTO:
        """Deprecated: Use model_validate() instead."""
        return cls.model_validate(data)


class JobSnapshotDTO(BaseModel):
    """Complete DTO for current job state (API response)."""

    model_config = ConfigDict(frozen=True, slots=True)

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

    def model_dump(self, **kwargs) -> dict[str, Any]:
        """Custom serialization - only include non-null/non-empty values."""
        data: dict[str, Any] = {
            "job_id": self.job_id,
            "book_id": self.book_id,
            "status": self.status,
            "percentage": self.percentage,
        }

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
    def model_validate(cls, data: dict[str, Any]) -> JobSnapshotDTO:
        """Custom deserialization from dict."""
        processed = {
            "job_id": str(data["job_id"]),
            "book_id": str(data["book_id"]),
            "status": str(data.get("status", "queued")),
            "percentage": int(data.get("percentage", 0)),
            "message": str(data.get("message", "")),
            "eta_seconds": data.get("eta_seconds"),
            "current_chapter": int(data.get("current_chapter", 0)),
            "total_chapters": int(data.get("total_chapters", 0)),
            "chapter_title": str(data.get("chapter_title", "")),
            "title": data.get("title"),
            "epub": data.get("epub"),
            "pdf": data.get("pdf"),
            "error": data.get("error"),
            "code": data.get("code"),
            "details": data.get("details"),
            "trace_log": data.get("trace_log"),
            "queue_position": data.get("queue_position"),
        }
        return super().model_validate(processed)

    # Backward compatibility aliases
    def to_dict(self) -> dict[str, Any]:
        """Deprecated: Use model_dump() instead."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobSnapshotDTO:
        """Deprecated: Use model_validate() instead."""
        return cls.model_validate(data)
