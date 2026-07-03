"""Python virtual environment & local server runtime helpers."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import config
from core import process_manager

if TYPE_CHECKING:
    from launcher._steps import Steps

REPO_ROOT: Path = Path(__file__).resolve().parent.parent

TIMEOUT_UV_SECONDS: int = int(os.getenv("RYLIOX_TIMEOUT_UV", "300"))
TIMEOUT_SUBPROCESS_SECONDS: int = int(os.getenv("RYLIOX_TIMEOUT_SUBPROCESS", "60"))

# Whitelisted runtime packages used to verify that the virtual environment is
# usable. The names here are also the literal strings passed to ``python -c``,
# so they MUST be hardcoded and pattern-checked — never built from a
# requirements file.
_PACKAGE_NAME_PATTERN: re.Pattern[str] = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_ALLOWED_RUNTIME_PACKAGES: frozenset[str] = frozenset(
    {
        "fastapi",
        "uvicorn",
        "bleach",
        "lxml",
        "httpx",
        "pydantic",
        "pydantic_settings",
        "fake_useragent",
        "cryptography",
        "jinja2",
        "markdown",
        "PIL",
        "weasyprint",
        "ebooklib",
        "starlette",
        "anyio",
        "h11",
        "certifi",
        "charset_normalizer",
        "idna",
        "urllib3",
        "yaml",
        "click",
        "rich",
        "pygments",
    }
)

RUN_DIR: Path = REPO_ROOT / ".run"
VENV_DIR: Path = Path(os.getenv("RYLIOX_VENV", RUN_DIR / "venv")).resolve()
PID_FILE: Path = RUN_DIR / "web-server.pid"
LOG_FILE: Path = RUN_DIR / "web-server.log"


def resolve_port(raw: str | None, default: int = 8000) -> int:
    try:
        parsed = int(raw) if raw else default
    except (TypeError, ValueError):
        print(f"  [WARN] Invalid port value {raw!r}, using default {default}")
        return default
    if not 1 <= parsed <= 65_535:
        print(f"  [WARN] Port {parsed} out of range, using default {default}")
        return default
    return parsed


def server_url(port: int) -> str:
    scheme = "https" if config.SETTINGS.security.enable_https_redirect else "http"
    return f"{scheme}://localhost:{port}"


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def server_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    venv_dir = VENV_DIR
    if env.get("VIRTUAL_ENV") != str(venv_dir):
        env["VIRTUAL_ENV"] = str(venv_dir)
    venv_bin = venv_dir / ("Scripts" if os.name == "nt" else "bin")
    venv_bin_str = str(venv_bin)
    path = env.get("PATH", "")
    head = path.split(os.pathsep)[0] if path else ""
    if head != venv_bin_str:
        env["PATH"] = f"{venv_bin_str}{os.pathsep}{path}" if path else venv_bin_str
    return env


def run_checked(
    command: list[str],
    step: str,
    cwd: Path | None = None,
    timeout: int | None = None,
    env: dict[str, str] | None = None,
) -> None:
    """Print the step and execute the command. Raises RuntimeError on failure."""
    print(step)
    try:
        subprocess.run(
            command,
            cwd=cwd or REPO_ROOT,
            env=env,
            check=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        stdout = exc.stdout.decode("utf-8", errors="replace") if exc.stdout else ""
        details = (stderr or stdout or "No output captured")[:500]
        raise RuntimeError(
            f"Command failed with exit code {exc.returncode}: {' '.join(command[:4])}\n"
            f"Error details: {details}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Command timed out after {timeout}s: {' '.join(command[:2])}") from exc
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Command executable not found: {command[0] if command else 'unknown'}"
        ) from exc


def require_uv() -> str:
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError(
            "uv not found in PATH. Install it to synchronize the Python environment."
        )
    return uv


def uv_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env["UV_PROJECT_ENVIRONMENT"] = str(VENV_DIR)
    return env


def _venv_has_runtime_dependencies(venv_python: Path) -> bool:
    """Verify the venv can import every whitelisted runtime package."""
    for name in sorted(_ALLOWED_RUNTIME_PACKAGES):
        if not _PACKAGE_NAME_PATTERN.match(name):
            print(f"  [WARN] Skipping invalid package name: {name}")
            continue
        result = subprocess.run(
            [str(venv_python), "-c", f"import {name}"],
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
            timeout=10,
        )
        if result.returncode != 0:
            return False
    return True


def ensure_python_runtime(steps: Steps) -> Path:
    venv = venv_python()
    uv = require_uv()

    if not venv.exists():
        _sync_venv(steps, uv, "Creating virtual environment and synchronising dependencies with uv...")
    else:
        steps.next("Virtual environment found.")

    if _venv_has_runtime_dependencies(venv):
        steps.next("Python dependencies already installed.")
    elif _sync_venv(steps, uv, "Installing/updating Python dependencies with uv..."):
        if not _venv_has_runtime_dependencies(venv):
            _recover_corrupt_venv(steps, uv)
    return venv


def _sync_venv(steps: Steps, uv: str, label: str) -> bool:
    try:
        run_checked(
            [uv, "sync", "--frozen"],
            steps.format(label),
            timeout=TIMEOUT_UV_SECONDS,
            env=uv_env(),
        )
        return True
    except RuntimeError:
        if VENV_DIR.exists():
            shutil.rmtree(VENV_DIR, ignore_errors=True)
        return False


def _recover_corrupt_venv(steps: Steps, uv: str) -> None:
    print("   [WARN] Virtual environment appears corrupt. Recreating from scratch...")
    if VENV_DIR.exists():
        shutil.rmtree(VENV_DIR, ignore_errors=True)
    run_checked(
        [uv, "sync", "--frozen"],
        steps.format("Recreating virtual environment with uv..."),
        timeout=TIMEOUT_UV_SECONDS,
        env=uv_env(),
    )


def clean_runtime_cache() -> bool:
    """Remove transient runtime files (queue DB, error logs)."""
    print(" - Cleaning runtime cache...")
    if not config.DATA_DIR.exists():
        print(f"   [INFO] DATA_DIR does not exist yet: {config.DATA_DIR}")
        return True
    if not config.DATA_DIR.is_dir():
        print(f"   [WARN] DATA_DIR is not a directory: {config.DATA_DIR}")
        return False

    cleaned: list[str] = []
    errors: list[str] = []
    files: list[Path] = []

    db_name = config.SETTINGS.queue.db_name or config.SETTINGS.download_db_name
    if db_name:
        files.append(config.DATA_DIR / db_name)

    log_dir_name = config.SETTINGS.queue.log_dir or config.SETTINGS.log_dir
    if log_dir_name:
        for log_file in (config.DATA_DIR / log_dir_name).glob("download-error-*.log"):
            files.append(log_file)

    for path in files:
        try:
            path.unlink()
            cleaned.append(path.name)
        except OSError as exc:
            errors.append(f"{path.name}: {exc}")
            print(f"   [WARN] Could not delete {path.name}: {exc}")

    if cleaned:
        print(f"   Deleted: {', '.join(cleaned)}")
    if errors:
        print(f"   Failed to delete {len(errors)} file(s)")
        return False
    if not cleaned:
        print("   Nothing to clean.")
    return True


def ensure_run_dir() -> None:
    RUN_DIR.mkdir(exist_ok=True)


def stop_port(steps: Steps, port: int) -> None:
    process_manager.stop_port(port, step_label=steps.format(f"Releasing localhost:{port}..."))


def launch_server(venv: Path, steps: Steps, label: str) -> None:
    """Launch the web server in the foreground (blocks until exit)."""
    steps.next(label)
    try:
        subprocess.run(
            [str(venv), "-X", "utf8", "-m", "web.server"],
            cwd=REPO_ROOT,
            env=server_env(),
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Server process exited with code {exc.returncode}. Check the server logs."
        ) from exc
    except KeyboardInterrupt:
        print("\n  Server stopped by user.")
        sys.exit(0)
    except Exception as exc:
        raise RuntimeError(f"Failed to launch server: {exc}") from exc


def run_status(port: int) -> None:
    process_manager.print_runtime_status(port=port, pid_file=PID_FILE, log_file=LOG_FILE)


def run_stop(port: int) -> None:
    process_manager.stop_background_server(port=port, pid_file=PID_FILE)
