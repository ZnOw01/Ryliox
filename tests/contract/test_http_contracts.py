from __future__ import annotations

from fastapi.testclient import TestClient

from web.server import create_app


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
