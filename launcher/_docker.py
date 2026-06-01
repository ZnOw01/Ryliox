"""Docker Compose launcher mode."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import TYPE_CHECKING

import config
from launcher._runtime import REPO_ROOT, run_checked, server_url

if TYPE_CHECKING:
    from launcher._steps import Steps

TIMEOUT_DOCKER_SECONDS: int = int(os.getenv("RYLIOX_TIMEOUT_DOCKER", "120"))


def detect_compose_command() -> tuple[list[str], bool]:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker is not installed or not available in PATH.")

    try:
        result = subprocess.run(
            [docker, "compose", "version"],
            capture_output=True,
            check=True,
            timeout=10,
        )
        if result.returncode == 0:
            return [docker, "compose"], True
    except subprocess.CalledProcessError as exc:
        if exc.returncode not in (1, 125):
            print(f"  [WARN] Docker compose check failed: {exc}")
    except subprocess.TimeoutExpired:
        print("  [WARN] Docker compose version check timed out")
    except FileNotFoundError:
        pass

    compose = shutil.which("docker-compose")
    if compose:
        return [compose], False
    raise RuntimeError("Neither Docker Compose plugin nor docker-compose found.")


def verify_running(compose: list[str]) -> None:
    try:
        result = subprocess.run(
            [*compose, "ps", "--services", "--filter", "status=running"],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
    except subprocess.CalledProcessError as exc:
        print(
            f"  [WARN] Could not verify containers. Check with: {' '.join(compose)} ps\n"
            f"Error: {exc.stderr[:200] if exc.stderr else 'Unknown error'}"
        )
        raise RuntimeError(
            f"Docker container verification failed with exit code {exc.returncode}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Docker container verification timed out after 15s") from exc

    if not result.stdout.strip():
        raise RuntimeError(f"No running containers found. Verify with: {' '.join(compose)} ps")


def run_docker(steps: Steps, port: int) -> None:
    compose_file = REPO_ROOT / "docker-compose.yml"
    if not compose_file.exists():
        raise RuntimeError("docker-compose.yml not found.")

    compose, is_plugin = detect_compose_command()
    quiet = "--quiet" if is_plugin else "-q"

    run_checked(
        [*compose, "-f", str(compose_file), "config", quiet],
        steps.format("Validating compose configuration..."),
        timeout=TIMEOUT_DOCKER_SECONDS,
    )
    run_checked(
        [*compose, "up", "-d"],
        steps.format("Starting containers..."),
        timeout=TIMEOUT_DOCKER_SECONDS,
    )
    verify_running(compose)

    print(f"\nServer available at {server_url(port)}")
    _ = config  # keep import explicit for future use
