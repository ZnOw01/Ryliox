"""The launcher bootstraps the project, so it must run before anything is installed."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from launcher import _runtime

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_launcher_imports_with_only_the_standard_library():
    # ``-S`` hides site-packages and ``-E`` ignores PYTHONPATH, so a third-party import fails.
    result = subprocess.run(
        [sys.executable, "-S", "-E", "-c", "import launcher"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_port_falls_back_to_the_default_before_the_environment_exists(monkeypatch, tmp_path):
    monkeypatch.setattr(_runtime, "VENV_DIR", tmp_path / "missing-venv")

    assert _runtime.server_port(None) == _runtime.DEFAULT_PORT
    assert _runtime.server_port(9100) == 9100
