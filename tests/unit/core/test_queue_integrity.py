from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from core.dto import DownloadErrorDTO, DownloadJobDTO, DownloadProgressDTO
from core.repository import DownloadJobRepository, UnitOfWork
from core.services import DownloadQueueService

if TYPE_CHECKING:
    from pathlib import Path


def _job(index: int, tmp_path: Path) -> DownloadJobDTO:
    return DownloadJobDTO.create(
        book_id=f"book-{index}",
        output_dir=tmp_path,
        formats=["epub"],
        selected_chapters=None,
        skip_images=False,
    )


def test_enqueue_if_capacity_is_atomic_across_repository_instances(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "queue.sqlite3"
    repositories = [DownloadJobRepository(db_path) for _ in range(8)]
    jobs = [_job(index, tmp_path) for index in range(8)]

    def enqueue(index: int) -> dict[str, object] | None:
        return repositories[index].enqueue_if_capacity(jobs[index], max_queued_jobs=2)

    with ThreadPoolExecutor(max_workers=8) as executor:
        snapshots = list(executor.map(enqueue, range(8)))

    assert sum(snapshot is not None for snapshot in snapshots) == 2
    assert DownloadJobRepository(db_path).count_queued() == 2


def test_claim_converts_legacy_cancelled_queue_entry(tmp_path: Path) -> None:
    repository = DownloadJobRepository(tmp_path / "queue.sqlite3")
    job = _job(1, tmp_path)
    repository.save(job)
    repository.update(job.job_id, {"cancel_requested": 1})

    assert repository.claim_next_queued() is None

    snapshot = repository.get_by_id(job.job_id)
    assert snapshot is not None
    assert snapshot["status"] == "cancelled"
    assert snapshot["code"] == "download_cancelled"


def test_requeue_inflight_is_atomic_and_preserves_cancellation(tmp_path: Path) -> None:
    repository = DownloadJobRepository(tmp_path / "queue.sqlite3")
    requeue_job = _job(1, tmp_path)
    cancelled_job = _job(2, tmp_path)
    repository.save(requeue_job)
    repository.save(cancelled_job)
    repository.update(requeue_job.job_id, {"status": "running"})
    repository.update(cancelled_job.job_id, {"status": "running", "cancel_requested": 1})

    repository.requeue_inflight()

    requeued = repository.get_by_id(requeue_job.job_id)
    cancelled = repository.get_by_id(cancelled_job.job_id)
    assert requeued is not None
    assert requeued["status"] == "queued"
    assert cancelled is not None
    assert cancelled["status"] == "cancelled"


def test_service_constructor_does_not_requeue_inflight_jobs(tmp_path: Path) -> None:
    repository = DownloadJobRepository(tmp_path / "queue.sqlite3")
    job = _job(1, tmp_path)
    repository.save(job)
    repository.update(job.job_id, {"status": "running"})

    async def kernel_factory() -> object:
        return object()

    DownloadQueueService(
        kernel_factory=kernel_factory,
        repository=repository,
        error_log_dir=tmp_path,
    )

    snapshot = repository.get_by_id(job.job_id)
    assert snapshot is not None
    assert snapshot["status"] == "running"


def test_only_one_service_can_start_for_the_same_database(tmp_path: Path) -> None:
    db_path = tmp_path / "queue.sqlite3"
    repository = DownloadJobRepository(db_path)
    job = _job(1, tmp_path)
    repository.save(job)

    async def kernel_factory() -> object:
        return object()

    first = DownloadQueueService(
        kernel_factory=kernel_factory,
        repository=repository,
        error_log_dir=tmp_path,
    )
    second = DownloadQueueService(
        kernel_factory=kernel_factory,
        db_path=db_path,
        error_log_dir=tmp_path,
    )

    first._worker_loop = lambda: first._stop_event.wait()
    first.start()
    repository.update(job.job_id, {"status": "running"})

    with pytest.raises(RuntimeError, match="already active"):
        second.start()

    snapshot = repository.get_by_id(job.job_id)
    assert snapshot is not None
    assert snapshot["status"] == "running"

    assert first.stop()
    second._worker_loop = lambda: second._stop_event.wait()
    second.start()
    assert second.stop()


def test_failed_start_releases_database_lock(tmp_path: Path) -> None:
    class FailingRepository(DownloadJobRepository):
        def requeue_inflight(self) -> None:
            raise RuntimeError("startup failure")

    db_path = tmp_path / "queue.sqlite3"

    async def kernel_factory() -> object:
        return object()

    failing = DownloadQueueService(
        kernel_factory=kernel_factory,
        repository=FailingRepository(db_path),
        error_log_dir=tmp_path,
    )
    with pytest.raises(RuntimeError, match="startup failure"):
        failing.start()

    recovered = DownloadQueueService(
        kernel_factory=kernel_factory,
        db_path=db_path,
        error_log_dir=tmp_path,
    )
    recovered._worker_loop = lambda: recovered._stop_event.wait()
    recovered.start()
    assert recovered.stop()


@pytest.mark.parametrize("terminal_status", ["completed", "error", "cancelled"])
def test_mark_failed_does_not_overwrite_terminal_jobs(terminal_status: str, tmp_path: Path) -> None:
    repository = DownloadJobRepository(tmp_path / f"{terminal_status}.sqlite3")
    job = _job(1, tmp_path)
    repository.save(job)
    repository.update(
        job.job_id,
        {"status": terminal_status, "error": "original", "code": "original_code"},
    )
    error = DownloadErrorDTO(
        error="replacement",
        code="replacement_code",
        details=None,
        trace_log=None,
    )

    assert repository.mark_failed(job.job_id, error) is False
    snapshot = repository.get_by_id(job.job_id)
    assert snapshot is not None
    assert snapshot["status"] == terminal_status
    assert snapshot["error"] == "original"
    assert snapshot["code"] == "original_code"


def test_cancel_is_rejected_after_job_enters_finalizing(tmp_path: Path) -> None:
    repository = DownloadJobRepository(tmp_path / "queue.sqlite3")
    job = _job(1, tmp_path)
    repository.save(job)
    repository.update(job.job_id, {"status": "running"})
    repository.update_progress(
        job.job_id,
        DownloadProgressDTO(status="finalizing", percentage=99),
    )

    outcome, snapshot = repository.request_cancel(job.job_id)

    assert outcome == "too_late"
    assert snapshot is not None
    assert snapshot["status"] == "finalizing"
    assert repository.is_cancel_requested(job.job_id) is False


def test_completed_race_does_not_degrade_terminal_job_to_error(tmp_path: Path) -> None:
    repository = DownloadJobRepository(tmp_path / "queue.sqlite3")
    job = _job(1, tmp_path)
    repository.save(job)
    repository.update(job.job_id, {"status": "completed"})

    class Downloader:
        async def download(self, **kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(
                book_id=job.book_id,
                title="Book",
                files={},
                chapters_count=1,
            )

    class Kernel(dict[str, object]):
        async def __aenter__(self) -> Kernel:
            return self

        async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
            return None

    async def kernel_factory() -> Kernel:
        return Kernel({"downloader": Downloader()})

    service = DownloadQueueService(
        kernel_factory=kernel_factory,
        repository=repository,
        error_log_dir=tmp_path,
    )
    service._run_job(job)

    snapshot = repository.get_by_id(job.job_id)
    assert snapshot is not None
    assert snapshot["status"] == "completed"


def test_unit_of_work_explicit_rollback_is_idempotent_inside_context() -> None:
    import sqlite3

    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE values_table (value INTEGER)")
    statements: list[str] = []
    connection.set_trace_callback(statements.append)

    with UnitOfWork(connection) as unit_of_work:
        connection.execute("INSERT INTO values_table VALUES (1)")
        unit_of_work.rollback()
        unit_of_work.rollback()

    assert unit_of_work._active is False
    assert statements.count("ROLLBACK") == 1
    assert connection.execute("SELECT COUNT(*) FROM values_table").fetchone() == (0,)


def test_unit_of_work_commit_is_idempotent_and_deactivates() -> None:
    import sqlite3

    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE values_table (value INTEGER)")
    statements: list[str] = []
    connection.set_trace_callback(statements.append)

    with UnitOfWork(connection) as unit_of_work:
        connection.execute("INSERT INTO values_table VALUES (1)")
        unit_of_work.commit()
        unit_of_work.commit()

    assert unit_of_work._active is False
    assert statements.count("COMMIT") == 1
    assert connection.execute("SELECT COUNT(*) FROM values_table").fetchone() == (1,)


def test_non_positive_queue_capacity_is_rejected(tmp_path: Path) -> None:
    async def kernel_factory() -> object:
        return object()

    with pytest.raises(ValueError, match="max_queued_jobs"):
        DownloadQueueService(
            kernel_factory=kernel_factory,
            repository=DownloadJobRepository(tmp_path / "queue.sqlite3"),
            error_log_dir=tmp_path,
            max_queued_jobs=0,
        )


class _CheckpointRepository(DownloadJobRepository):
    def __init__(self, db_path: Path):
        super().__init__(db_path)
        self.progress_updates = 0

    def update_progress(self, job_id: str, progress: DownloadProgressDTO) -> bool:
        self.progress_updates += 1
        updated = super().update_progress(job_id, progress)
        self.request_cancel(job_id)
        return updated


class _Kernel(dict[str, object]):
    async def __aenter__(self) -> _Kernel:
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        return None


def test_progress_checkpoint_checks_cancel_before_and_after_persisting(
    tmp_path: Path,
) -> None:
    repository = _CheckpointRepository(tmp_path / "queue.sqlite3")
    job = _job(1, tmp_path)
    repository.save(job)
    seen_cancel_check = False

    class Downloader:
        async def download(self, **kwargs: object) -> SimpleNamespace:
            nonlocal seen_cancel_check
            assert kwargs["job_id"] == job.job_id
            cancel_check = kwargs["cancel_check"]
            seen_cancel_check = callable(cancel_check)
            progress_callback = kwargs["progress_callback"]
            assert callable(progress_callback)
            progress_callback(
                SimpleNamespace(
                    status="running",
                    percentage=10,
                    message="checkpoint",
                    eta_seconds=None,
                    current_chapter=1,
                    total_chapters=2,
                    chapter_title="Chapter 1",
                )
            )
            return SimpleNamespace(
                book_id=job.book_id,
                title="Book",
                files={},
                chapters_count=2,
            )

    async def kernel_factory() -> _Kernel:
        return _Kernel({"downloader": Downloader()})

    service = DownloadQueueService(
        kernel_factory=kernel_factory,
        repository=repository,
        error_log_dir=tmp_path,
    )
    service._run_job(job)

    snapshot = repository.get_by_id(job.job_id)
    assert seen_cancel_check is True
    assert repository.progress_updates == 1
    assert snapshot is not None
    assert snapshot["status"] == "cancelled"


def test_service_requeues_inflight_jobs_only_when_starting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository = DownloadJobRepository(tmp_path / "queue.sqlite3")
    job = _job(1, tmp_path)
    repository.save(job)
    repository.update(job.job_id, {"status": "running"})
    queue_sizes: list[int] = []
    active_downloads: list[int] = []

    import core.services as services_module

    monkeypatch.setattr(services_module.metrics, "set_queue_size", queue_sizes.append)
    monkeypatch.setattr(services_module.metrics, "set_active_downloads", active_downloads.append)

    async def kernel_factory() -> object:
        return object()

    service = DownloadQueueService(
        kernel_factory=kernel_factory,
        repository=repository,
        error_log_dir=tmp_path,
    )

    snapshot = repository.get_by_id(job.job_id)
    assert snapshot is not None
    assert snapshot["status"] == "running"
    assert queue_sizes[-1] == 0
    assert active_downloads[-1] == 1

    service._worker_loop = lambda: service._stop_event.wait()
    service.start()
    snapshot = repository.get_by_id(job.job_id)
    assert snapshot is not None
    assert snapshot["status"] == "queued"
    service._sync_metrics()
    assert queue_sizes[-1] == 1
    assert active_downloads[-1] == 0
    assert service.stop()


def test_download_timeout_is_reported_with_an_explanation(tmp_path: Path) -> None:
    import asyncio

    repository = DownloadJobRepository(tmp_path / "queue.sqlite3")
    job = _job(1, tmp_path)
    repository.save(job)

    class Downloader:
        async def download(self, **kwargs: object) -> SimpleNamespace:
            await asyncio.sleep(5)
            raise AssertionError("unreachable")

    async def kernel_factory() -> _Kernel:
        return _Kernel({"downloader": Downloader()})

    service = DownloadQueueService(
        kernel_factory=kernel_factory,
        repository=repository,
        error_log_dir=tmp_path,
        download_timeout_seconds=1,
    )
    service._run_job(job)

    snapshot = repository.get_by_id(job.job_id)
    assert snapshot is not None
    assert snapshot["status"] == "error"
    assert "did not finish within 1 seconds" in snapshot["error"]
    assert "REQUEST_TIMEOUT_SECONDS" in snapshot["error"]


def test_shutdown_mid_download_leaves_job_resumable(tmp_path: Path) -> None:
    """A server shutdown is not a user cancel: the job resumes on the next start."""
    repository = DownloadJobRepository(tmp_path / "queue.sqlite3")
    job = _job(1, tmp_path)
    repository.save(job)
    claimed = repository.claim_next_queued()
    assert claimed is not None

    service: DownloadQueueService

    class Downloader:
        async def download(self, **kwargs: object) -> SimpleNamespace:
            progress_callback = kwargs["progress_callback"]
            assert callable(progress_callback)
            service._stop_event.set()  # what stop() does while a job is running
            progress_callback(
                SimpleNamespace(
                    status="running",
                    percentage=40,
                    message="working",
                    eta_seconds=None,
                    current_chapter=2,
                    total_chapters=5,
                    chapter_title="Chapter 2",
                )
            )
            raise AssertionError("unreachable")

    async def kernel_factory() -> _Kernel:
        return _Kernel({"downloader": Downloader()})

    service = DownloadQueueService(
        kernel_factory=kernel_factory,
        repository=repository,
        error_log_dir=tmp_path,
    )
    service._run_job(claimed)

    snapshot = repository.get_by_id(job.job_id)
    assert snapshot is not None
    assert snapshot["status"] not in {"cancelled", "error", "completed"}

    repository.requeue_inflight()
    snapshot = repository.get_by_id(job.job_id)
    assert snapshot is not None
    assert snapshot["status"] == "queued"


def test_user_cancel_during_shutdown_still_cancels(tmp_path: Path) -> None:
    repository = DownloadJobRepository(tmp_path / "queue.sqlite3")
    job = _job(1, tmp_path)
    repository.save(job)
    claimed = repository.claim_next_queued()
    assert claimed is not None

    service: DownloadQueueService

    class Downloader:
        async def download(self, **kwargs: object) -> SimpleNamespace:
            assert repository.request_cancel(job.job_id)[0] == "cancel_requested"
            service._stop_event.set()
            cancel_check = kwargs["cancel_check"]
            assert callable(cancel_check)
            assert cancel_check() is True
            from core.contracts import DownloadCancelledError

            raise DownloadCancelledError("Download cancelled by user")

    async def kernel_factory() -> _Kernel:
        return _Kernel({"downloader": Downloader()})

    service = DownloadQueueService(
        kernel_factory=kernel_factory,
        repository=repository,
        error_log_dir=tmp_path,
    )
    service._run_job(claimed)

    snapshot = repository.get_by_id(job.job_id)
    assert snapshot is not None
    assert snapshot["status"] == "cancelled"


def test_shutdown_after_publication_still_completes_the_job(tmp_path: Path) -> None:
    """A book that was already published must not be reported as cancelled."""
    repository = DownloadJobRepository(tmp_path / "queue.sqlite3")
    job = _job(1, tmp_path)
    repository.save(job)
    claimed = repository.claim_next_queued()
    assert claimed is not None

    service: DownloadQueueService

    class Downloader:
        async def download(self, **kwargs: object) -> SimpleNamespace:
            service._stop_event.set()  # shutdown begins right after publication
            return SimpleNamespace(
                book_id=job.book_id, title="Book", files={"epub": "x.epub"}, chapters_count=1
            )

    async def kernel_factory() -> _Kernel:
        return _Kernel({"downloader": Downloader()})

    service = DownloadQueueService(
        kernel_factory=kernel_factory,
        repository=repository,
        error_log_dir=tmp_path,
    )
    service._run_job(claimed)

    snapshot = repository.get_by_id(job.job_id)
    assert snapshot is not None
    assert snapshot["status"] == "completed"
