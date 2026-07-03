from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient

from web.server import _mount_static, create_app

if TYPE_CHECKING:
    from pathlib import Path


def test_contract_progress_endpoint_shape() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/progress")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, dict)
    assert "status" in payload


def test_contract_openapi_available() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert isinstance(schema, dict)
    assert "paths" in schema


def test_contract_frontend_dist_assets_are_served(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dist = tmp_path / "frontend" / "dist"
    (dist / "_astro").mkdir(parents=True)
    (dist / "icons").mkdir()
    (dist / "locales").mkdir()
    (dist / "index.html").write_text("<html>Ryliox</html>", encoding="utf-8")
    (dist / "_astro" / "app.js").write_text("console.log('ok')", encoding="utf-8")
    (dist / "manifest.json").write_text("{}", encoding="utf-8")
    (dist / "locales" / "es.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr("web.server.config.REPO_ROOT", tmp_path)
    app = FastAPI()
    _mount_static(app)

    with TestClient(app) as client:
        assert client.get("/_astro/app.js").status_code == 200
        assert client.get("/manifest.json").status_code == 200
        assert client.get("/locales/es.json").status_code == 200
        assert client.get("/settings").text == "<html>Ryliox</html>"

        api_response = client.get("/api/missing")

    assert api_response.status_code == 404
    assert api_response.headers["content-type"].startswith("application/json")
