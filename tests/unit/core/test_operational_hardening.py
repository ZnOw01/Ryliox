from __future__ import annotations

import asyncio
import sqlite3
import threading
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI, Request

import config
import core.audit as audit_module
from core.audit import AuditEventType, AuditLogger
from core.secrets import SecretManager, SecretManagerError
from core.services import DownloadQueueService, QueueCapacityError
from core.session_store import SessionStore
from plugins.pdf import restricted_url_fetcher
from web.server import RequestBodyLimitMiddleware, create_app

if TYPE_CHECKING:
    from pathlib import Path


def test_plaintext_cookie_database_is_migrated_in_place(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "session.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """CREATE TABLE session_cookie_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, value TEXT NOT NULL,
                domain TEXT, path TEXT NOT NULL DEFAULT '/', secure INTEGER NOT NULL DEFAULT 0,
                http_only INTEGER NOT NULL DEFAULT 0, expires INTEGER, same_site TEXT,
                updated_at REAL NOT NULL)"""
        )
        conn.execute(
            "INSERT INTO session_cookie_records(name, value, path, updated_at) VALUES (?, ?, '/', 1)",
            ("session", "plaintext-secret"),
        )
    monkeypatch.setattr(config.SETTINGS.session, "encryption_key", Fernet.generate_key().decode())

    store = SessionStore(db_path=db_path, legacy_cookies_file=tmp_path / "cookies.json")

    assert store.get_cookies() == {"session": "plaintext-secret"}
    assert b"plaintext-secret" not in db_path.read_bytes()
    assert db_path.stat().st_mode & 0o777 == 0o600


def test_pdf_fetcher_blocks_network_and_file_traversal(tmp_path: Path) -> None:
    book_dir = tmp_path / "book"
    book_dir.mkdir()
    asset = book_dir / "image.svg"
    asset.write_text("<svg/>", encoding="utf-8")
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    fetch = restricted_url_fetcher(book_dir)

    assert fetch.fetch(asset.as_uri())
    with pytest.raises(ValueError, match="scheme"):
        fetch.fetch("http://127.0.0.1:8000/private")
    with pytest.raises(ValueError, match="outside"):
        fetch.fetch(outside.as_uri())


@pytest.mark.asyncio
async def test_request_body_limit_counts_chunked_body() -> None:
    app = FastAPI()
    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=5)

    @app.post("/")
    async def consume(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    async def chunks():
        yield b"123"
        yield b"456"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/", content=chunks())

    assert response.status_code == 413
    assert response.json()["code"] == "request_too_large"


def test_remote_bind_requires_admin_token(monkeypatch) -> None:
    monkeypatch.setattr(config.SETTINGS.server, "host", "0.0.0.0")
    monkeypatch.setattr(config.SETTINGS.security, "admin_token", None)

    with pytest.raises(RuntimeError, match="ADMIN_TOKEN"):
        create_app()


@pytest.mark.asyncio
async def test_remote_api_accepts_only_configured_bearer_token(monkeypatch) -> None:
    token = "t" * 32
    monkeypatch.setattr(config.SETTINGS.server, "host", "0.0.0.0")
    monkeypatch.setattr(config.SETTINGS.security, "admin_token", token)
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        denied = await client.get("/api/openapi.json")
        allowed = await client.get(
            "/api/openapi.json", headers={"Authorization": f"Bearer {token}"}
        )

    assert denied.status_code == 401
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_remote_admin_session_authenticates_sse_compatible_cookie(monkeypatch) -> None:
    token = "s" * 32
    monkeypatch.setattr(config.SETTINGS.server, "host", "0.0.0.0")
    monkeypatch.setattr(config.SETTINGS.security, "admin_token", token)
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        denied = await client.get("/api/openapi.json")
        login = await client.post("/api/admin/session", json={"token": token})
        allowed = await client.get("/api/openapi.json")

    assert denied.status_code == 401
    assert login.status_code == 200
    assert login.cookies.get("ryliox_admin_session")
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_progress_notification_is_async_and_thread_safe(tmp_path: Path) -> None:
    repository = MagicMock()
    repository.requeue_inflight.return_value = None

    async def kernel_factory():
        return MagicMock()

    service = DownloadQueueService(
        kernel_factory=kernel_factory,
        repository=repository,
        error_log_dir=tmp_path,
    )
    version = service.get_progress_version()
    waiter = asyncio.create_task(service.wait_for_progress_change_async(version, 1))
    await asyncio.sleep(0)
    thread = threading.Thread(target=service._notify_progress_change)
    thread.start()
    thread.join()

    assert await waiter == version + 1


def test_queue_capacity_is_enforced_before_persistence(tmp_path: Path) -> None:
    repository = MagicMock()
    repository.count_queued.return_value = 1

    async def kernel_factory():
        return MagicMock()

    service = DownloadQueueService(
        kernel_factory=kernel_factory,
        repository=repository,
        error_log_dir=tmp_path,
        max_queued_jobs=1,
    )

    with pytest.raises(QueueCapacityError):
        service.enqueue(
            book_id="book",
            output_dir=tmp_path,
            formats=["epub"],
            selected_chapters=None,
            skip_images=False,
        )
    repository.save.assert_not_called()


def test_worker_shutdown_does_not_close_repository_while_thread_is_alive(tmp_path: Path) -> None:
    repository = MagicMock()

    async def kernel_factory():
        return MagicMock()

    service = DownloadQueueService(
        kernel_factory=kernel_factory,
        repository=repository,
        error_log_dir=tmp_path,
    )
    worker = MagicMock()
    worker.is_alive.return_value = True
    service._worker = worker

    assert service.stop(timeout_seconds=0.1) is False
    repository.close.assert_not_called()


def test_audit_chain_restores_across_logger_restart(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(audit_module, "_audit_hmac_key", b"a" * 64)
    monkeypatch.setattr(AuditLogger, "_instance", None)
    log_file = tmp_path / "audit.log"
    first = AuditLogger(log_file=log_file, enabled=True)
    first.log(AuditEventType.CONFIG_CHANGED, "first_change")
    last_hash = first._last_hash

    AuditLogger._instance = None
    restored = AuditLogger(log_file=log_file, enabled=True)
    entries = restored.search()

    assert entries[-1].prev_hash == last_hash
    assert restored.verify_integrity()[0] is True


def test_secret_manager_refuses_ephemeral_master_password(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("SECRET_MASTER_PASSWORD", raising=False)
    monkeypatch.setattr(SecretManager, "_instance", None)
    monkeypatch.setattr(SecretManager, "_initialized", False)
    manager = SecretManager(
        secrets_file=tmp_path / "secrets.enc",
        master_key_file=tmp_path / "master.salt",
    )

    with pytest.raises(SecretManagerError, match="required"):
        manager.set("example", "value")
    assert not (tmp_path / "secrets.enc").exists()
