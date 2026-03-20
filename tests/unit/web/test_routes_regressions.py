from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from web.server import create_app

pytestmark = pytest.mark.unit


class DummyKernel:
    def __init__(self, **plugins) -> None:
        self._plugins = plugins
        self.http = SimpleNamespace(close=self._close)

    async def _close(self) -> None:
        return None

    def __getitem__(self, name: str):
        return self._plugins[name]


def _build_client(monkeypatch: pytest.MonkeyPatch, *, kernel: DummyKernel | None = None, queue=None):
    def fake_initialize(app):
        app.state.session_store = object()
        app.state.kernel = kernel or DummyKernel(
            auth=SimpleNamespace(get_status=lambda: {"valid": False}),
            book=SimpleNamespace(),
            chapters=SimpleNamespace(),
            output=SimpleNamespace(validate_dir=lambda path: (True, "ok", Path(path)), get_default_dir=lambda: Path(".")),
            system=SimpleNamespace(show_folder_picker=lambda _current: None),
        )
        app.state.download_queue = queue or SimpleNamespace(
            get_progress=lambda job_id=None: {},
            get_progress_version=lambda: 0,
            wait_for_progress_change=lambda previous, timeout: previous,
        )

    async def fake_shutdown(_app):
        return None

    monkeypatch.setattr("web.server.initialize_app_services", fake_initialize)
    monkeypatch.setattr("web.server.shutdown_app_services", fake_shutdown)
    return TestClient(create_app())


def test_api_404_uses_stable_error_envelope(monkeypatch: pytest.MonkeyPatch):
    with _build_client(monkeypatch) as client:
        response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]
    assert response.json()["code"] == "http_error"


def test_book_endpoint_returns_json_envelope_for_invalid_upstream_payload(monkeypatch: pytest.MonkeyPatch):
    class BookPlugin:
        async def fetch(self, _book_id: str):
            return {"id": "demo", "virtual_pages": -1}

    with _build_client(monkeypatch, kernel=DummyKernel(book=BookPlugin(), chapters=SimpleNamespace(), auth=SimpleNamespace(get_status=lambda: {"valid": False}), output=SimpleNamespace(validate_dir=lambda path: (True, "ok", Path(path)), get_default_dir=lambda: Path(".")), system=SimpleNamespace(show_folder_picker=lambda _current: None))) as client:
        response = client.get("/api/book/demo")

    assert response.status_code == 502
    assert response.json() == {
        "error": "Invalid book data returned by upstream service.",
        "code": "book_fetch_failed",
    }


def test_progress_with_unknown_job_id_returns_not_found(monkeypatch: pytest.MonkeyPatch):
    queue = SimpleNamespace(
        get_progress=lambda job_id=None: {},
        get_progress_version=lambda: 0,
        wait_for_progress_change=lambda previous, timeout: previous,
    )
    with _build_client(monkeypatch, queue=queue) as client:
        response = client.get("/api/progress?job_id=missing", headers={"origin": "http://testserver"})

    assert response.status_code == 404
    assert response.json()["code"] == "job_not_found"


def test_browse_output_dir_validates_before_persisting(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    output = SimpleNamespace(
        validate_dir=lambda path: (False, "bad path", Path(path)),
        get_default_dir=lambda: tmp_path,
    )
    async def fake_show_folder_picker(_current):
        return str(tmp_path / "picked")

    system = SimpleNamespace(show_folder_picker=fake_show_folder_picker)
    kernel = DummyKernel(
        auth=SimpleNamespace(get_status=lambda: {"valid": False}),
        book=SimpleNamespace(),
        chapters=SimpleNamespace(),
        output=output,
        system=system,
    )

    with _build_client(monkeypatch, kernel=kernel) as client:
        response = client.post(
            "/api/settings/output-dir",
            json={"browse": True},
            headers={"origin": "http://testserver"},
        )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_output_dir"
