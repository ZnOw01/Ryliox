"""Pydantic API contracts for FastAPI endpoints with OWASP validation.

Naming convention:
  - ``*Request``  : inbound request body (validated strictly, no extra fields).
  - ``*Response`` : outbound payload (extra fields ignored on construction).

Implements OWASP A03: Input validation and injection prevention.
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from core.validators import (
    validate_book_id,
    validate_filename,
    validate_user_input,
    MAX_INPUT_LENGTH,
    ValidationError,
)


class _RequestModel(BaseModel):
    """Base model for all inbound request payloads."""

    model_config = ConfigDict(extra="forbid")


class _ResponseModel(BaseModel):
    """Base model for all outbound response payloads."""

    model_config = ConfigDict(extra="ignore")


class AckResponse(_ResponseModel):
    """Generic acknowledgement payload."""

    success: bool
    message: str | None = None


SaveCookiesResponse = AckResponse
CancelResponse = AckResponse
RevealResponse = AckResponse


class ErrorResponse(_ResponseModel):
    """Stable error envelope used by error paths."""

    error: str
    code: str
    details: dict[str, Any] | None = None


class HealthResponse(_ResponseModel):
    status: str
    uptime_seconds: float
    version: str


class StatusResponse(_ResponseModel):
    valid: bool
    reason: str | None = None
    has_cookies: bool


class SettingsResponse(_ResponseModel):
    output_dir: str


class SearchResponse(_ResponseModel):
    results: list[dict[str, Any]]


class BookInfoResponse(_ResponseModel):
    id: str
    ourn: str | None = None
    title: str | None = None
    authors: list[Any] = Field(default_factory=list)
    publishers: list[Any] = Field(default_factory=list)
    description: str | None = None
    cover_url: str | None = None
    isbn: str | None = None
    language: str | None = None
    publication_date: str | None = None
    virtual_pages: int | None = Field(default=None, ge=0)
    chapters_url: str | None = None
    toc_url: str | None = None
    spine_url: str | None = None
    files_url: str | None = None


class ChapterSummaryResponse(_ResponseModel):
    index: int
    title: str
    pages: int | None = Field(default=None, ge=1)
    minutes: float | None = Field(default=None, ge=0.0)


class BookChaptersResponse(_ResponseModel):
    chapters: list[ChapterSummaryResponse]

    @computed_field  # type: ignore[misc]
    @property
    def total(self) -> int:
        """Total derived from the list; avoids desynchronization."""
        return len(self.chapters)


class FormatsResponse(_ResponseModel):
    formats: list[str]
    aliases: dict[str, str]
    book_only: list[str]
    descriptions: dict[str, str]


class CookiesResponse(_ResponseModel):
    cookies: dict[str, str]


class DownloadStartResponse(_ResponseModel):
    status: str
    book_id: str | None = None
    job_id: str
    queue_position: int | None = None


class _ProgressBase(_ResponseModel):
    """Common fields for all progress states."""

    job_id: str
    book_id: str | None = None


class IdleProgress(_ProgressBase):
    status: Literal["idle"] = "idle"
    job_id: str = ""  # idle no tiene job activo; string vacío es válido aquí


class QueuedProgress(_ProgressBase):
    status: Literal["queued"]
    queue_position: int = Field(ge=0)


class RunningProgress(_ProgressBase):
    status: Literal["running"]
    percentage: int = Field(ge=0, le=100)
    message: str | None = None
    eta_seconds: int | None = Field(default=None, ge=0)
    current_chapter: int | None = Field(default=None, ge=1)
    total_chapters: int | None = Field(default=None, ge=1)
    chapter_title: str | None = None
    title: str | None = None


class CompletedProgress(_ProgressBase):
    status: Literal["completed"]
    title: str | None = None
    epub: str | None = None
    pdf: list[str] | None = None

    @field_validator("pdf", mode="before")
    @classmethod
    def _normalize_pdf(cls, value: Any) -> list[str] | None:
        """Accepts str or list[str] for compatibility with legacy responses."""
        if value is None:
            return None
        if isinstance(value, str):
            return [value]
        return value


class CancelledProgress(_ProgressBase):
    status: Literal["cancelled"]
    error: str
    code: str | None = None
    details: dict[str, Any] | None = None
    trace_log: str | None = None


class ErrorProgress(_ProgressBase):
    status: Literal["error"]
    error: str
    code: str | None = None
    details: dict[str, Any] | None = None
    trace_log: str | None = None


ProgressResponse = Annotated[
    IdleProgress | QueuedProgress | RunningProgress | CompletedProgress | CancelledProgress | ErrorProgress,
    Field(discriminator="status"),
]


class CancelRequest(_RequestModel):
    job_id: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("job_id", mode="after")
    @classmethod
    def _validate_job_id(cls, v: str | None) -> str | None:
        """Validate job_id format for injection prevention."""
        if v is None:
            return v
        # Only allow alphanumeric, hyphen, and underscore
        if not re.match(r"^[\w\-]+$", v):
            raise ValueError("job_id contains invalid characters")
        return v


class RevealRequest(_RequestModel):
    path: str | None = Field(default=None, min_length=1, max_length=500)

    @field_validator("path", mode="after")
    @classmethod
    def _validate_path(cls, v: str | None) -> str | None:
        """Validate path for path traversal prevention."""
        if v is None:
            return v
        # Check for path traversal attempts
        if ".." in v or "~" in v:
            raise ValueError("path contains invalid sequence")
        # Check for null bytes
        if "\x00" in v:
            raise ValueError("path contains null bytes")
        return v


class SetOutputDirResponse(_ResponseModel):
    path: str | None = None
    cancelled: bool = False


class OutputDirRequest(_RequestModel):
    browse: bool = False
    path: str | None = Field(default=None, min_length=1, max_length=500)

    @field_validator("path", mode="after")
    @classmethod
    def _validate_path(cls, v: str | None) -> str | None:
        """Validate output directory path."""
        if v is None:
            return v
        # Check for path traversal
        if ".." in v or "~" in v:
            raise ValueError("path contains invalid sequence")
        # Check for null bytes
        if "\x00" in v:
            raise ValueError("path contains null bytes")
        return v


class DownloadRequest(_RequestModel):
    book_id: str | None = Field(default=None, min_length=10, max_length=50)
    format: list[str] = Field(default_factory=lambda: ["epub"])
    chapters: list[int] | None = None
    output_dir: str | None = Field(default=None, min_length=1, max_length=500)
    skip_images: bool = False

    @field_validator("book_id", mode="after")
    @classmethod
    def _validate_book_id(cls, v: str | None) -> str | None:
        """Validate book_id format (urn:orm:book:*)."""
        if v is None:
            return v
        try:
            return validate_book_id(v)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("format", mode="before")
    @classmethod
    def _normalize_format(cls, value: Any) -> list[str]:
        """Normalizes format to list[str]; accepts str, tuple, set, and legacy list."""
        if value is None:
            return ["epub"]
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("format must not be empty")
            return [stripped]
        if isinstance(value, (list, tuple, set)):
            clean = [str(item).strip() for item in value if str(item).strip()]
            if not clean:
                raise ValueError("format list must contain at least one value")
            return clean
        raise ValueError(
            "format must be a string or an array of strings (for example: 'epub' or ['epub','pdf'])"
        )

    @field_validator("output_dir", mode="after")
    @classmethod
    def _validate_output_dir(cls, v: str | None) -> str | None:
        """Validate output directory path."""
        if v is None:
            return v
        # Check for path traversal
        if ".." in v or "~" in v:
            raise ValueError("output_dir contains invalid sequence")
        if "\x00" in v:
            raise ValueError("output_dir contains null bytes")
        return v

    @model_validator(mode="after")
    def _validate_chapters(self) -> DownloadRequest:
        """Chapter indexes must be >= 0 if provided."""
        if self.chapters is not None:
            invalid = [c for c in self.chapters if c < 0]
            if invalid:
                raise ValueError(f"Invalid chapter indexes (must be >= 0): {invalid}")
        return self
