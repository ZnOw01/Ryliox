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
    get_port,
    interactive_mode,
    open_browser_async,
    parse_args,
    resolve_mode,
    safe_error,
    server_url,
)
from launcher._runtime import (
    clean_runtime_cache,
    ensure_python_runtime,
    ensure_run_dir,
    launch_server,
    run_status,
    run_stop,
    stop_port,
)
from launcher._steps import Steps

if TYPE_CHECKING:
    from collections.abc import Callable

REPO_ROOT = _cli.REPO_ROOT

# Steps for the interactive-mode loop (which does not pre-print totals).
_INTERACTIVE_STEPS: Callable[[], Steps] = lambda: Steps(total=6)


# ── Mode implementations ────────────────────────────────────────────────────


def _run_backend_only(port: int, open_browser: bool) -> None:
    steps = Steps(total=4)
    stop_port(steps, port)
    steps.next("Mode: backend only")
    venv = ensure_python_runtime(steps)
    if not clean_runtime_cache():
        print("   [WARN] Cache cleanup had errors, but continuing...")
    if open_browser:
        open_browser_async(server_url(port))
    launch_server(venv, steps, label=f"Starting API at {server_url(port)}...")


def _run_unified(port: int, open_browser: bool, rebuild: bool) -> None:
    steps = Steps(total=6)
    stop_port(steps, port)
    steps.next("Mode: unified")
    venv = ensure_python_runtime(steps)
    _frontend.ensure_build(steps, rebuild=rebuild)
    if not clean_runtime_cache():
        print("   [WARN] Cache cleanup had errors, but continuing...")
    if open_browser:
        open_browser_async(server_url(port))
    launch_server(venv, steps, label=f"Starting unified server at {server_url(port)}...")


def _run_docker(port: int, open_browser: bool) -> None:
    steps = Steps(total=4)
    stop_port(steps, port)
    steps.next("Mode: Docker Compose")
    _docker.run_docker(steps, port)
    if open_browser:
        open_browser_async(server_url(port))


# ── Dispatch ────────────────────────────────────────────────────────────────


def _build_dispatch(port: int, open_browser: bool, rebuild: bool) -> dict[str, Callable[[], None]]:
    return {
        "quit": lambda: None,
        "status": lambda: run_status(port),
        "stop": lambda: run_stop(port),
        "docker": lambda: _run_docker(port, open_browser),
        "backend_only": lambda: _run_backend_only(port, open_browser),
        "unified": lambda: _run_unified(port, open_browser, rebuild),
    }


# ── Main entry point ────────────────────────────────────────────────────────


def main() -> int:
    try:
        os.chdir(REPO_ROOT)
        argv = sys.argv[1:]
        args = parse_args(argv)
        port = get_port(args)
        open_browser = not args.no_browser
        ensure_run_dir()
        dispatch = _build_dispatch(port, open_browser, args.rebuild_frontend)

        if not argv:
            banner()
            return _interactive_loop(dispatch, port)

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


def _interactive_loop(dispatch: dict[str, Callable[[], None]], port: int) -> int:
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
            stop_port(_INTERACTIVE_STEPS(), port)
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
        print("\n" + "─" * 44 + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
