"""The launcher bootstraps the project, so it must run before anything is installed."""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import time
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


_SIGTERM_DRIVER = """
import sys
from pathlib import Path
from launcher import _runtime
from launcher._steps import Steps

_runtime.LOG_FILE = Path(sys.argv[2])
_runtime.launch_server(Path(sys.argv[1]), 8765, Steps(total=1), label="start")
"""


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signal semantics")
def test_sigterm_stops_the_server_child(tmp_path):
    pid_file = tmp_path / "server.pid"
    fake_server = tmp_path / "fake-python"
    fake_server.write_text(f'#!/bin/sh\necho $$ > "{pid_file}"\nexec sleep 60\n')
    fake_server.chmod(0o755)

    launcher = subprocess.Popen(
        [sys.executable, "-c", _SIGTERM_DRIVER, str(fake_server), str(tmp_path / "server.log")],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 10
        while not pid_file.exists() or not pid_file.read_text().strip():
            assert time.monotonic() < deadline, "fake server never started"
            time.sleep(0.05)
        child_pid = int(pid_file.read_text())

        launcher.send_signal(signal.SIGTERM)
        launcher.wait(timeout=30)

        deadline = time.monotonic() + 5
        while _runtime._processes.is_process_alive(child_pid):
            assert time.monotonic() < deadline, "server child outlived the launcher"
            time.sleep(0.05)
    finally:
        launcher.kill()
        if pid_file.exists() and pid_file.read_text().strip():
            with contextlib.suppress(ProcessLookupError):
                os.kill(int(pid_file.read_text()), signal.SIGKILL)
