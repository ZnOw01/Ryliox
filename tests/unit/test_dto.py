from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from core.dto import (
    DownloadErrorDTO,
    DownloadJobDTO,
    DownloadProgressDTO,
    DownloadResultDTO,
    JobSnapshotDTO,
)

pytestmark = pytest.mark.unit


class TestDownloadJobDTO:
    def test_creation_with_basic_fields(self):
        dto = DownloadJobDTO(book_id="book-123", output_dir=Path("/tmp/output"))
        assert dto.book_id == "book-123"
        assert dto.output_dir == Path("/tmp/output")
        assert dto.formats == ["epub"]
        assert dto.selected_chapters is None
        assert dto.skip_images is False
        assert len(dto.job_id) == 32  # 16 bytes hex

    def test_job_id_is_auto_generated(self):
        dto1 = DownloadJobDTO(book_id="b1", output_dir=Path("/tmp"))
        dto2 = DownloadJobDTO(book_id="b2", output_dir=Path("/tmp"))
        assert dto1.job_id != dto2.job_id

    def test_output_dir_string_is_normalized(self):
        dto = DownloadJobDTO(book_id="book-123", output_dir="/tmp/output")
        assert isinstance(dto.output_dir, Path)
        assert dto.output_dir == Path("/tmp/output")

    def test_formats_defaults_to_epub(self):
        dto = DownloadJobDTO(book_id="b1", output_dir=Path("/tmp"))
        assert dto.formats == ["epub"]

    def test_custom_formats(self):
        dto = DownloadJobDTO(book_id="b1", output_dir=Path("/tmp"), formats=["pdf", "epub"])
        assert dto.formats == ["pdf", "epub"]

    def test_selected_chapters(self):
        dto = DownloadJobDTO(book_id="b1", output_dir=Path("/tmp"), selected_chapters=[0, 1, 2])
        assert dto.selected_chapters == [0, 1, 2]

    def test_skip_images(self):
        dto = DownloadJobDTO(book_id="b1", output_dir=Path("/tmp"), skip_images=True)
        assert dto.skip_images is True

    def test_model_dump_serializes_path_as_string(self):
        dto = DownloadJobDTO(book_id="b1", output_dir=Path("/tmp/output"))
        dumped = dto.model_dump()
        assert dumped["output_dir"] == "/tmp/output"
        assert isinstance(dumped["output_dir"], str)

    def test_model_dump_handles_selected_chapters(self):
        dto = DownloadJobDTO(book_id="b1", output_dir=Path("/tmp"), selected_chapters=[0, 1])
        dumped = dto.model_dump()
        assert dumped["selected_chapters"] == [0, 1]

    def test_model_dump_none_selected_chapters(self):
        dto = DownloadJobDTO(book_id="b1", output_dir=Path("/tmp"))
        dumped = dto.model_dump()
        assert "selected_chapters" not in dumped

    def test_model_validate_round_trip(self):
        original = DownloadJobDTO(book_id="b1", output_dir=Path("/tmp/output"))
        data = original.model_dump()
        restored = DownloadJobDTO.model_validate(data)
        assert restored.job_id == original.job_id
        assert restored.book_id == original.book_id
        assert restored.output_dir == original.output_dir
        assert restored.formats == original.formats

    def test_model_validate_with_extra_data(self):
        data = {
            "job_id": "abc123",
            "book_id": "book-1",
            "output_dir": "/tmp/out",
            "formats": ["pdf"],
        }
        dto = DownloadJobDTO.model_validate(data)
        assert dto.job_id == "abc123"
        assert dto.output_dir == Path("/tmp/out")

    def test_model_validate_without_formats(self):
        data = {"book_id": "b1", "output_dir": "/tmp"}
        dto = DownloadJobDTO.model_validate(data)
        assert dto.formats == ["epub"]

    def test_create_factory_method(self):
        dto = DownloadJobDTO.create(book_id="b1", output_dir=Path("/tmp"))
        assert dto.book_id == "b1"
        assert len(dto.job_id) == 32

    def test_to_dict_backward_compat(self):
        dto = DownloadJobDTO(book_id="b1", output_dir=Path("/tmp"))
        assert dto.to_dict() == dto.model_dump()

    def test_from_dict_backward_compat(self):
        data = {"book_id": "b1", "output_dir": "/tmp"}
        dto = DownloadJobDTO.from_dict(data)
        assert dto.book_id == "b1"

    def test_frozen_prevents_mutation(self):
        dto = DownloadJobDTO(book_id="b1", output_dir=Path("/tmp"))
        with pytest.raises(ValidationError):
            dto.book_id = "changed"

    def test_missing_book_id_fails(self):
        with pytest.raises(ValidationError):
            DownloadJobDTO(output_dir=Path("/tmp"))

    def test_missing_output_dir_fails(self):
        with pytest.raises(ValidationError):
            DownloadJobDTO(book_id="b1")

    def test_model_validate_selected_chapters_as_list(self):
        data = {
            "book_id": "b1",
            "output_dir": "/tmp",
            "selected_chapters": [0, 2, 5],
        }
        dto = DownloadJobDTO.model_validate(data)
        assert dto.selected_chapters == [0, 2, 5]

    def test_model_validate_selected_chapters_none(self):
        data = {"book_id": "b1", "output_dir": "/tmp"}
        dto = DownloadJobDTO.model_validate(data)
        assert dto.selected_chapters is None

    def test_model_validate_skip_images_default(self):
        data = {"book_id": "b1", "output_dir": "/tmp"}
        dto = DownloadJobDTO.model_validate(data)
        assert dto.skip_images is False

    def test_model_validate_skip_images_true(self):
        data = {"book_id": "b1", "output_dir": "/tmp", "skip_images": True}
        dto = DownloadJobDTO.model_validate(data)
        assert dto.skip_images is True


class TestDownloadProgressDTO:
    def test_creation_with_defaults(self):
        dto = DownloadProgressDTO()
        assert dto.status == "queued"
        assert dto.percentage == 0
        assert dto.message == ""
        assert dto.eta_seconds is None
        assert dto.current_chapter == 0
        assert dto.total_chapters == 0
        assert dto.chapter_title == ""
        assert dto.queue_position is None

    def test_creation_with_values(self):
        dto = DownloadProgressDTO(
            status="downloading",
            percentage=50,
            message="Downloading chapter 3",
            eta_seconds=120,
            current_chapter=3,
            total_chapters=10,
            chapter_title="Advanced Topics",
            queue_position=None,
        )
        assert dto.status == "downloading"
        assert dto.percentage == 50
        assert dto.message == "Downloading chapter 3"
        assert dto.eta_seconds == 120
        assert dto.current_chapter == 3
        assert dto.total_chapters == 10
        assert dto.chapter_title == "Advanced Topics"

    def test_with_updates_creates_new_instance(self):
        dto1 = DownloadProgressDTO(status="queued")
        dto2 = dto1.with_updates(status="downloading", percentage=10)
        assert dto1.status == "queued"
        assert dto2.status == "downloading"
        assert dto2.percentage == 10
        assert dto1 is not dto2

    def test_with_updates_preserves_unchanged_fields(self):
        dto1 = DownloadProgressDTO(status="queued", current_chapter=0, total_chapters=5)
        dto2 = dto1.with_updates(status="downloading")
        assert dto2.current_chapter == 0
        assert dto2.total_chapters == 5

    def test_with_updates_queue_position(self):
        dto1 = DownloadProgressDTO(queue_position=1)
        dto2 = dto1.with_updates(queue_position=2)
        assert dto2.queue_position == 2
        assert dto1.queue_position == 1

    def test_model_dump_excludes_empty_and_none(self):
        dto = DownloadProgressDTO()
        dumped = dto.model_dump()
        assert "eta_seconds" not in dumped
        assert "queue_position" not in dumped
        assert dumped["status"] == "queued"

    def test_model_dump_includes_eta_when_set(self):
        dto = DownloadProgressDTO(eta_seconds=30)
        dumped = dto.model_dump()
        assert dumped["eta_seconds"] == 30

    def test_model_dump_includes_queue_position_when_set(self):
        dto = DownloadProgressDTO(queue_position=1)
        dumped = dto.model_dump()
        assert dumped["queue_position"] == 1

    def test_model_dump_excludes_empty_message(self):
        dto = DownloadProgressDTO(message="")
        dumped = dto.model_dump()
        assert "message" not in dumped

    def test_model_dump_includes_non_empty_message(self):
        dto = DownloadProgressDTO(message="Working...")
        dumped = dto.model_dump()
        assert dumped["message"] == "Working..."

    def test_model_validate_round_trip(self):
        original = DownloadProgressDTO(
            status="downloading",
            percentage=75,
            message="Almost done",
            eta_seconds=10,
            current_chapter=7,
            total_chapters=10,
            chapter_title="Final Chapter",
            queue_position=1,
        )
        data = original.model_dump()
        restored = DownloadProgressDTO.model_validate(data)
        assert restored.status == original.status
        assert restored.percentage == original.percentage
        assert restored.message == original.message
        assert restored.eta_seconds == original.eta_seconds
        assert restored.current_chapter == original.current_chapter
        assert restored.total_chapters == original.total_chapters
        assert restored.chapter_title == original.chapter_title
        assert restored.queue_position == original.queue_position

    def test_model_validate_with_minimal_data(self):
        dto = DownloadProgressDTO.model_validate({"status": "completed"})
        assert dto.status == "completed"
        assert dto.percentage == 0

    def test_to_dict_backward_compat(self):
        dto = DownloadProgressDTO(status="downloading")
        assert dto.to_dict() == dto.model_dump()

    def test_from_dict_backward_compat(self):
        dto = DownloadProgressDTO.from_dict({"status": "completed", "percentage": 100})
        assert dto.status == "completed"
        assert dto.percentage == 100

    def test_frozen_prevents_mutation(self):
        dto = DownloadProgressDTO(status="queued")
        with pytest.raises(ValidationError):
            dto.status = "downloading"

    def test_completed_status(self):
        dto = DownloadProgressDTO(
            status="completed",
            percentage=100,
            message="Download complete",
        )
        assert dto.status == "completed"
        assert dto.percentage == 100


class TestDownloadResultDTO:
    def test_creation_with_basic_fields(self):
        dto = DownloadResultDTO(book_id="b1", title="Test Book")
        assert dto.book_id == "b1"
        assert dto.title == "Test Book"
        assert dto.epub_path is None
        assert dto.pdf_paths is None
        assert dto.chapters_count == 0

    def test_with_epub_path(self):
        dto = DownloadResultDTO(
            book_id="b1",
            title="Test Book",
            epub_path="/tmp/output/book.epub",
        )
        assert dto.epub_path == "/tmp/output/book.epub"

    def test_with_string_pdf_path(self):
        dto = DownloadResultDTO(
            book_id="b1",
            title="Test Book",
            pdf_paths="/tmp/output/book.pdf",
        )
        assert dto.pdf_paths == "/tmp/output/book.pdf"

    def test_with_list_pdf_paths(self):
        paths = ["/tmp/output/ch1.pdf", "/tmp/output/ch2.pdf"]
        dto = DownloadResultDTO(
            book_id="b1",
            title="Test Book",
            pdf_paths=paths,
        )
        assert dto.pdf_paths == paths
        assert len(dto.pdf_paths) == 2

    def test_with_none_pdf_path(self):
        dto = DownloadResultDTO(
            book_id="b1",
            title="Test Book",
            pdf_paths=None,
        )
        assert dto.pdf_paths is None

    def test_with_chapters_count(self):
        dto = DownloadResultDTO(
            book_id="b1",
            title="Test Book",
            chapters_count=10,
        )
        assert dto.chapters_count == 10

    def test_model_dump_includes_optional_epub(self):
        dto = DownloadResultDTO(
            book_id="b1",
            title="Test",
            epub_path="/tmp/book.epub",
        )
        dumped = dto.model_dump()
        assert dumped["epub"] == "/tmp/book.epub"
        assert "pdf" not in dumped

    def test_model_dump_includes_optional_pdf(self):
        dto = DownloadResultDTO(
            book_id="b1",
            title="Test",
            pdf_paths="/tmp/book.pdf",
        )
        dumped = dto.model_dump()
        assert dumped["pdf"] == "/tmp/book.pdf"

    def test_model_dump_excludes_missing_optionals(self):
        dto = DownloadResultDTO(book_id="b1", title="Test")
        dumped = dto.model_dump()
        assert "epub" not in dumped
        assert "pdf" not in dumped

    def test_model_validate_round_trip(self):
        original = DownloadResultDTO(
            book_id="b1",
            title="Test",
            epub_path="/tmp/book.epub",
            pdf_paths=["/tmp/p1.pdf", "/tmp/p2.pdf"],
            chapters_count=5,
        )
        data = original.model_dump()
        restored = DownloadResultDTO.model_validate(data)
        assert restored.book_id == original.book_id
        assert restored.title == original.title
        assert restored.epub_path == original.epub_path
        assert restored.pdf_paths == original.pdf_paths
        assert restored.chapters_count == original.chapters_count

    def test_model_validate_with_epub_key(self):
        dto = DownloadResultDTO.model_validate(
            {"book_id": "b1", "title": "T", "epub": "/tmp/book.epub"}
        )
        assert dto.epub_path == "/tmp/book.epub"

    def test_model_validate_with_pdf_key_string(self):
        dto = DownloadResultDTO.model_validate(
            {"book_id": "b1", "title": "T", "pdf": "/tmp/book.pdf"}
        )
        assert dto.pdf_paths == "/tmp/book.pdf"

    def test_model_validate_with_pdf_key_list(self):
        dto = DownloadResultDTO.model_validate(
            {"book_id": "b1", "title": "T", "pdf": ["/tmp/p1.pdf", "/tmp/p2.pdf"]}
        )
        assert dto.pdf_paths == ["/tmp/p1.pdf", "/tmp/p2.pdf"]

    def test_to_dict_backward_compat(self):
        dto = DownloadResultDTO(book_id="b1", title="T", epub_path="/tmp/book.epub")
        assert dto.to_dict() == dto.model_dump()

    def test_from_dict_backward_compat(self):
        dto = DownloadResultDTO.from_dict({"book_id": "b1", "title": "T", "epub": "/tmp/book.epub"})
        assert dto.epub_path == "/tmp/book.epub"


class TestDownloadErrorDTO:
    def test_creation_with_required_fields(self):
        dto = DownloadErrorDTO(error="Something went wrong")
        assert dto.error == "Something went wrong"
        assert dto.code == "unknown_error"
        assert dto.details is None
        assert dto.trace_log is None

    def test_with_all_fields(self):
        dto = DownloadErrorDTO(
            error="Connection failed",
            code="connection_error",
            details={"url": "https://example.com"},
            trace_log="Traceback (most recent call last)...",
        )
        assert dto.error == "Connection failed"
        assert dto.code == "connection_error"
        assert dto.details == {"url": "https://example.com"}
        assert dto.trace_log == "Traceback (most recent call last)..."

    def test_with_optional_details(self):
        dto = DownloadErrorDTO(error="Not found", code="not_found", details={"id": "123"})
        assert dto.details == {"id": "123"}

    def test_without_optional_details(self):
        dto = DownloadErrorDTO(error="Error")
        assert dto.details is None

    def test_with_optional_trace_log(self):
        dto = DownloadErrorDTO(error="Error", trace_log="trace details")
        assert dto.trace_log == "trace details"

    def test_without_optional_trace_log(self):
        dto = DownloadErrorDTO(error="Error")
        assert dto.trace_log is None

    def test_model_dump_includes_all_fields(self):
        dto = DownloadErrorDTO(
            error="err",
            code="err_code",
            details={"key": "val"},
            trace_log="trace",
        )
        dumped = dto.model_dump()
        assert dumped["error"] == "err"
        assert dumped["code"] == "err_code"
        assert dumped["details"] == {"key": "val"}
        assert dumped["trace_log"] == "trace"

    def test_model_dump_excludes_optional_when_none(self):
        dto = DownloadErrorDTO(error="err")
        dumped = dto.model_dump()
        assert "details" not in dumped
        assert "trace_log" not in dumped

    def test_model_validate_round_trip(self):
        original = DownloadErrorDTO(
            error="err",
            code="code",
            details={"a": 1},
            trace_log="stack",
        )
        data = original.model_dump()
        restored = DownloadErrorDTO.model_validate(data)
        assert restored.error == original.error
        assert restored.code == original.code
        assert restored.details == original.details
        assert restored.trace_log == original.trace_log

    def test_model_validate_with_defaults(self):
        dto = DownloadErrorDTO.model_validate({"error": "err"})
        assert dto.error == "err"
        assert dto.code == "unknown_error"

    def test_model_validate_with_code(self):
        dto = DownloadErrorDTO.model_validate({"error": "err", "code": "custom"})
        assert dto.code == "custom"

    def test_to_dict_backward_compat(self):
        dto = DownloadErrorDTO(error="err", code="c")
        assert dto.to_dict() == dto.model_dump()

    def test_from_dict_backward_compat(self):
        dto = DownloadErrorDTO.from_dict({"error": "err", "code": "c"})
        assert dto.error == "err"
        assert dto.code == "c"

    def test_heterogeneous_details_dict(self):
        dto = DownloadErrorDTO(
            error="err",
            details={"str": "val", "int": 42, "list": [1, 2], "none": None},
        )
        assert dto.details["str"] == "val"
        assert dto.details["int"] == 42


class TestJobSnapshotDTO:
    def test_creation_with_basic_fields(self):
        dto = JobSnapshotDTO(job_id="j1", book_id="b1", status="queued")
        assert dto.job_id == "j1"
        assert dto.book_id == "b1"
        assert dto.status == "queued"

    def test_model_dump_only_includes_non_empty(self):
        dto = JobSnapshotDTO(job_id="j1", book_id="b1", status="queued")
        dumped = dto.model_dump()
        assert dumped["job_id"] == "j1"
        assert dumped["book_id"] == "b1"
        assert dumped["status"] == "queued"
        assert "message" not in dumped
        assert "eta_seconds" not in dumped

    def test_model_dump_includes_eta_when_set(self):
        dto = JobSnapshotDTO(job_id="j1", book_id="b1", status="downloading", eta_seconds=30)
        dumped = dto.model_dump()
        assert dumped["eta_seconds"] == 30

    def test_model_validate_round_trip(self):
        original = JobSnapshotDTO(
            job_id="j1",
            book_id="b1",
            status="completed",
            percentage=100,
            title="Test Book",
            epub="/tmp/book.epub",
        )
        data = original.model_dump()
        restored = JobSnapshotDTO.model_validate(data)
        assert restored.job_id == original.job_id
        assert restored.book_id == original.book_id
        assert restored.status == original.status

    def test_to_dict_backward_compat(self):
        dto = JobSnapshotDTO(job_id="j1", book_id="b1", status="queued")
        assert dto.to_dict() == dto.model_dump()

    def test_from_dict_backward_compat(self):
        dto = JobSnapshotDTO.from_dict({"job_id": "j1", "book_id": "b1", "status": "queued"})
        assert dto.job_id == "j1"
