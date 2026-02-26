"""Pydantic API contracts for FastAPI endpoints.

Naming convention:
  - ``*Request``  : inbound request body (validated strictly, no extra fields).
  - ``*Response`` : outbound payload (extra fields ignored on construction).
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
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
        """Total derivado de la lista; evita desincronización."""
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
    """Campos comunes a todos los estados de progreso."""

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
        """Acepta str o list[str] por compatibilidad con respuestas legacy."""
        if value is None:
            return None
        if isinstance(value, str):
            return [value]
        return value


class ErrorProgress(_ProgressBase):
    status: Literal["error"]
    error: str
    code: str | None = None
    details: dict[str, Any] | None = None
    trace_log: str | None = None


ProgressResponse = Annotated[
    IdleProgress | QueuedProgress | RunningProgress | CompletedProgress | ErrorProgress,
    Field(discriminator="status"),
]


class CancelRequest(_RequestModel):
    job_id: str | None = Field(default=None, min_length=1)


class RevealRequest(_RequestModel):
    path: str | None = Field(default=None, min_length=1)


class SetOutputDirResponse(_ResponseModel):
    path: str | None = None
    cancelled: bool = False


class OutputDirRequest(_RequestModel):
    browse: bool = False
    path: str | None = Field(default=None, min_length=1)


class DownloadRequest(_RequestModel):
    book_id: str | None = Field(default=None, min_length=1)
    format: list[str] = Field(default_factory=lambda: ["epub"])
    chapters: list[int] | None = None
    output_dir: str | None = Field(default=None, min_length=1)
    skip_images: bool = False

    @field_validator("format", mode="before")
    @classmethod
    def _normalize_format(cls, value: Any) -> list[str]:
        """Normaliza formato a list[str]; acepta str, tuple, set y list legacy."""
        if value is None:
            return ["epub"]
        if isinstance(value, str):
            stripped = value.strip()
            return [stripped] if stripped else ["epub"]
        if isinstance(value, (list, tuple, set)):
            clean = [str(item).strip() for item in value if str(item).strip()]
            return clean if clean else ["epub"]
        return ["epub"]

    @model_validator(mode="after")
    def _validate_chapters(self) -> DownloadRequest:
        """Los índices de capítulo deben ser >= 0 si se proporcionan."""
        if self.chapters is not None:
            invalid = [c for c in self.chapters if c < 0]
            if invalid:
                raise ValueError(
                    f"Índices de capítulo inválidos (deben ser >= 0): {invalid}"
                )
        return self
