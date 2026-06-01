"""Interactive menu & CLI dispatch for the launcher."""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

import config
from launcher._runtime import REPO_ROOT, resolve_port, server_url

MODES: dict[str, str] = {
    "1": "unified",
    "2": "stop",
    "3": "status",
    "4": "docker",
    "q": "quit",
}

MODE_LABELS: dict[str, str] = {
    "unified": "1) Unified application on :8000 (recommended)",
    "stop": "2) Stop running services",
    "status": "3) Show runtime status",
    "docker": "4) Docker mode",
}


def is_stdin_interactive() -> bool:
    try:
        return sys.stdin.isatty()
    except (AttributeError, OSError):
        return False


def open_browser_async(url: str, delay: float = 1.5) -> None:
    def _open() -> None:
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception as exc:
            print(f"  [WARN] Could not open browser: {exc}")

    thread = threading.Thread(target=_open, daemon=True)
    thread.start()


def interactive_mode() -> str:
    if not is_stdin_interactive():
        print("  (stdin is not TTY, default mode: unified)")
        return "unified"
    print("Select mode:")
    for label in MODE_LABELS.values():
        print(f"  {label}")
    print("  q) Exit")
    try:
        choice = input("Option [1]: ").strip().lower() or "1"
    except (EOFError, OSError):
        print("  (stdin unavailable, using default mode: unified)")
        return "unified"
    mode = MODES.get(choice)
    if mode is None:
        print(f"  [WARN] Unrecognised option {choice!r}, using default mode: unified")
        return "unified"
    return mode


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m launcher")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--stop", action="store_true")
    mode.add_argument("--docker", action="store_true")
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--backend-only", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--rebuild-frontend", action="store_true")
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Server port (overrides PORT env var and default)",
    )
    return parser.parse_args(argv)


def resolve_mode(argv: list[str], args: argparse.Namespace) -> str:
    if not argv:
        return interactive_mode()
    if args.status:
        return "status"
    if args.stop:
        return "stop"
    if args.docker:
        return "docker"
    if args.backend_only:
        return "backend_only"
    return "unified"


def safe_error(exc: Exception) -> str:
    msg = str(exc)
    if REPO_ROOT.as_posix() in msg:
        msg = msg.replace(REPO_ROOT.as_posix(), "<REPO_ROOT>")
    home = str(Path.home())
    if home in msg:
        msg = msg.replace(home, "<HOME>")
    return f"{type(exc).__name__}: {msg}"


def banner() -> None:
    print()
    print("==========================================")
    print(" Ryliox Launcher")
    print("==========================================")
    print()


def get_port(args: argparse.Namespace) -> int:
    if args.port is not None:
        return resolve_port(str(args.port))
    return resolve_port(os.getenv("PORT", str(config.SETTINGS.server.port)))


__all__ = [
    "MODES",
    "MODE_LABELS",
    "is_stdin_interactive",
    "open_browser_async",
    "interactive_mode",
    "parse_args",
    "resolve_mode",
    "safe_error",
    "banner",
    "get_port",
    "server_url",
]
