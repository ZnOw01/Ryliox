"""Find and stop the processes listening on the server port."""

from __future__ import annotations

import csv
import os
import re
import shutil
import signal
import subprocess  # nosec B404
import time
from io import StringIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def is_process_alive(pid: int) -> bool:
    """Return True when a process PID exists and appears alive."""
    if pid <= 0:
        return False

    if os.name == "nt":
        result = subprocess.run(  # nosec B603 B607
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return False

        reader = csv.reader(StringIO(result.stdout))
        for row in reader:
            if len(row) < 2:
                continue
            try:
                if int(str(row[1]).strip()) == pid:
                    return True
            except ValueError:
                continue
        return False

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _address_matches_port(address: str, expected_port: int) -> bool:
    match = re.search(r":(\d+)$", address.strip())
    if not match:
        return False
    return int(match.group(1)) == expected_port


def _find_listener_pids_windows(port: int) -> set[int]:
    pids: set[int] = set()
    result = subprocess.run(  # nosec B603 B607
        ["netstat", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
        check=False,
    )

    for line in result.stdout.splitlines():
        normalized = line.strip()
        upper = normalized.upper()
        if not upper.startswith("TCP"):
            continue
        parts = normalized.split()
        if len(parts) < 5:
            continue

        local_address = parts[1]
        foreign_address = parts[2]
        if not _address_matches_port(local_address, port):
            continue
        if not _address_matches_port(foreign_address, 0):
            continue

        if parts[-1].isdigit():
            pids.add(int(parts[-1]))

    return pids


def _find_listener_pids_posix(port: int) -> set[int]:
    pids: set[int] = set()

    if shutil.which("lsof"):
        result = subprocess.run(  # nosec B603 B607
            ["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            check=False,
        )
        for value in result.stdout.split():
            if value.isdigit():
                pids.add(int(value))
        if pids:
            return pids

    if shutil.which("fuser"):
        result = subprocess.run(  # nosec B603 B607
            ["fuser", f"{port}/tcp"],
            capture_output=True,
            text=True,
            check=False,
        )
        matches = re.findall(r"\d+", f"{result.stdout} {result.stderr}")
        pids.update(int(match) for match in matches if match.isdigit())
        if pids:
            return pids

    if shutil.which("ss"):
        result = subprocess.run(  # nosec B603 B607
            ["ss", "-ltnp"],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in result.stdout.splitlines():
            normalized = line.strip()
            if not normalized:
                continue
            if not re.search(rf":{port}\b", normalized):
                continue
            for match in re.findall(r"pid=(\d+)", normalized):
                if match.isdigit():
                    pids.add(int(match))
        if pids:
            return pids

    if shutil.which("netstat"):
        result = subprocess.run(  # nosec B603 B607
            ["netstat", "-ltnp"],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in result.stdout.splitlines():
            normalized = line.strip()
            if not normalized:
                continue
            if "LISTEN" not in normalized.upper():
                continue
            parts = normalized.split()
            if len(parts) < 7:
                continue
            local_address = parts[3]
            pid_program = parts[6]
            if not _address_matches_port(local_address, port):
                continue
            pid_match = re.match(r"(\d+)", pid_program)
            if pid_match:
                pids.add(int(pid_match.group(1)))

    return pids


def find_listener_pids(port: int) -> set[int]:
    """Return process IDs currently listening on the given TCP port."""
    if os.name == "nt":
        return _find_listener_pids_windows(port)
    return _find_listener_pids_posix(port)


def stop_pid(pid: int) -> None:
    """Terminate a process by PID, escalating when required."""
    if pid == os.getpid() or pid <= 0:
        return

    if os.name == "nt":
        result = subprocess.run(  # nosec B603 B607
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 and is_process_alive(pid):
            details = (result.stderr or result.stdout or "taskkill failed").strip()
            raise RuntimeError(f"Failed to terminate process {pid}: {details}")
        return

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except PermissionError as exc:
        raise RuntimeError(f"No permission to terminate process {pid}.") from exc

    for _ in range(5):
        if not is_process_alive(pid):
            return
        time.sleep(0.2)

    force_signal = getattr(signal, "SIGKILL", signal.SIGTERM)
    try:
        os.kill(pid, force_signal)
    except ProcessLookupError:
        return
    except PermissionError as exc:
        raise RuntimeError(f"No permission to force-kill process {pid}.") from exc


def stop_port(port: int, step_label: str) -> None:
    """Stop all listener processes currently bound to a TCP port."""
    print(step_label)
    pids = find_listener_pids(port)

    if not pids:
        print(f" - No running listener on port {port}.")
        return

    for pid in sorted(pids):
        try:
            stop_pid(pid)
            if pid in find_listener_pids(port):
                print(f" - Could not stop process {pid}: still listening on {port}.")
            else:
                print(f" - Stopped process {pid}.")
        except RuntimeError as exc:
            print(f" - Could not stop process {pid}: {exc}")


def print_runtime_status(port: int, log_file: Path) -> None:
    """Print which processes listen on the server port and where the log is."""
    pids = sorted(find_listener_pids(port))
    print("[status] Runtime listeners")
    print(f" - Backend ({port}): {'up' if pids else 'down'}")
    if pids:
        print(f"   PIDs: {', '.join(str(pid) for pid in pids)}")
    print(f" - Backend log: {log_file if log_file.exists() else 'not created yet'}")
