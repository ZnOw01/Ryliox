"""Ryliox local launcher.

Wires together the small modules that bootstrap the Python venv, build the
Astro/React frontend, manage the local web server, and run Docker Compose.
The entry point is :func:`main`.
"""

from __future__ import annotations

import os
import subprocess
import sys
import traceback
from typing import TYPE_CHECKING

from launcher import _cli, _docker, _frontend
from launcher._cli import (
    banner,
    interactive_mode,
    open_browser_async,
    parse_args,
    resolve_mode,
    safe_error,
)
from launcher._runtime import (
    ensure_python_runtime,
    ensure_run_dir,
    launch_server,
    run_status,
    run_stop,
    server_port,
    server_url,
    stop_port,
)
from launcher._steps import Steps

if TYPE_CHECKING:
    from collections.abc import Callable

REPO_ROOT = _cli.REPO_ROOT

# Docker Compose publishes this port; see docker-compose.yml.
_DOCKER_PORT = 8000


# ── Mode implementations ────────────────────────────────────────────────────


def _run_unified(requested_port: int | None, open_browser: bool, rebuild: bool) -> None:
    steps = Steps(total=6)
    steps.next("Mode: unified")
    venv = ensure_python_runtime(steps)
    port = server_port(requested_port)
    stop_port(steps, port)
    _frontend.ensure_build(steps, rebuild=rebuild)
    if open_browser:
        open_browser_async(server_url(port))
    launch_server(venv, port, steps, label=f"Starting unified server at {server_url(port)}...")


def _run_docker(open_browser: bool) -> None:
    steps = Steps(total=4)
    stop_port(steps, _DOCKER_PORT)
    steps.next("Mode: Docker Compose")
    _docker.run_docker(steps, _DOCKER_PORT)
    if open_browser:
        open_browser_async(server_url(_DOCKER_PORT))


# ── Dispatch ────────────────────────────────────────────────────────────────


def _build_dispatch(
    requested_port: int | None, open_browser: bool, rebuild: bool
) -> dict[str, Callable[[], None]]:
    return {
        "quit": lambda: None,
        "status": lambda: run_status(server_port(requested_port)),
        "stop": lambda: run_stop(server_port(requested_port)),
        "docker": lambda: _run_docker(open_browser),
        "unified": lambda: _run_unified(requested_port, open_browser, rebuild),
    }


# ── Main entry point ────────────────────────────────────────────────────────


def main() -> int:
    try:
        os.chdir(REPO_ROOT)
        argv = sys.argv[1:]
        args = parse_args(argv)
        open_browser = not args.no_browser
        ensure_run_dir()
        dispatch = _build_dispatch(args.port, open_browser, args.rebuild_frontend)

        if not argv:
            banner()
            return _interactive_loop(dispatch)

        mode = resolve_mode(argv, args)
        if mode == "quit":
            return 0
        action = dispatch.get(mode)
        if action is None:
            raise ValueError(f"Unknown mode: {mode!r}")
        action()
        return 0

    except KeyboardInterrupt:
        print("\nCancelled by user.")
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"\nERROR: Command failed with exit code {exc.returncode}.")
        print(f"       {safe_error(exc)}")
        return 1
    except RuntimeError as exc:
        print(f"\nERROR: {safe_error(exc)}")
        return 1
    except OSError as exc:
        print(f"\nERROR: I/O error ({safe_error(exc)})")
        return 1
    except Exception as exc:
        print(f"\nUNEXPECTED ERROR ({type(exc).__name__}): {safe_error(exc)}")
        print("Please report this error including the full traceback.")
        traceback.print_exc()
        return 1


def _interactive_loop(dispatch: dict[str, Callable[[], None]]) -> int:
    while True:
        mode = interactive_mode()
        if mode == "quit":
            print("  Goodbye.")
            return 0
        action = dispatch.get(mode)
        if action is None:
            print(f"  [WARN] Unknown mode: {mode!r}")
            continue
        try:
            print()
            ensure_run_dir()
            action()
        except KeyboardInterrupt:
            print("\n  Stopped.")
        except subprocess.CalledProcessError as exc:
            print(f"\nERROR: Command failed with exit code {exc.returncode}.")
            print(f"       {safe_error(exc)}")
        except RuntimeError as exc:
            print(f"\nERROR: {safe_error(exc)}")
        except OSError as exc:
            print(f"\nERROR: I/O error ({safe_error(exc)})")
        except ValueError as exc:
            print(f"\nERROR: Invalid value ({safe_error(exc)})")
        print("\n" + "=" * 44 + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
