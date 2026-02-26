from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "path",
    [
        "/api/health",
        "/api/status",
        "/api/formats",
        "/api/progress",
    ],
)
def test_api_smoke_endpoints(app_client, path):
    assert app_client.get(path).status_code == 200
