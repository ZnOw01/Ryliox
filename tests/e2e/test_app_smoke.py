from __future__ import annotations

from fastapi.testclient import TestClient

from web.server import create_app


def test_e2e_health_and_status_smoke() -> None:
    with TestClient(create_app()) as client:
        health = client.get("/api/health")
        status = client.get("/api/status")

    assert health.status_code == 200
    assert status.status_code == 200
