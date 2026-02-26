from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from web.server import create_app


@pytest.fixture(scope="module")
def app_client():
    with TestClient(create_app()) as client:
        yield client
