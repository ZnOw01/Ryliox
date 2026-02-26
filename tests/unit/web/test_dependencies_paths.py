from __future__ import annotations

import pytest

import config
from web.dependencies import DOWNLOAD_ERROR_LOG_DIR, DOWNLOAD_QUEUE_DB

pytestmark = pytest.mark.unit


def test_launcher_paths_follow_config_data_dir():
    assert DOWNLOAD_QUEUE_DB == config.DATA_DIR / "download_jobs.sqlite3"
    assert DOWNLOAD_ERROR_LOG_DIR == config.DATA_DIR / "logs"
