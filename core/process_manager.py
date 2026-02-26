"""Process and port management utilities for local runtime launcher."""

from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path


def is_process_alive(pid: int) -> bool:
    """Return True when a process PID exists and appears alive."""
    if pid <= 0:
        return False

    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in result.stdout

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
    result = subprocess.run(
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
        result = subprocess.run(
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
        result = subprocess.run(
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
        result = subprocess.run(
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
        result = subprocess.run(
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


def is_port_listening(port: int) -> bool:
    """Return True when any process is listening on the given port."""
    return bool(find_listener_pids(port))


def wait_until_port_listening(
    port: int,
    timeout_seconds: float = 20.0,
    poll_interval: float = 0.2,
) -> bool:
    """Poll until a TCP port is listening or timeout expires."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if is_port_listening(port):
            return True
        time.sleep(poll_interval)
    return is_port_listening(port)


def first_listener_pid(port: int) -> int | None:
    """Return the first listener PID for a port, if any."""
    pids = sorted(find_listener_pids(port))
    return pids[0] if pids else None


def start_background_process(
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    log_file: Path,
) -> None:
    """Spawn a detached background process and append stdout/stderr to a log file."""
    log_file.parent.mkdir(exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as log_handle:
        popen_kwargs: dict = {"cwd": cwd, "stdout": log_handle, "stderr": log_handle, "env": env}
        if os.name == "nt":
            popen_kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
            )
        else:
            popen_kwargs["start_new_session"] = True

        subprocess.Popen(command, **popen_kwargs)


def write_background_pid(pid_file: Path, pid: int) -> None:
    """Write launcher-managed background PID to file."""
    pid_file.parent.mkdir(exist_ok=True)
    pid_file.write_text(str(pid), encoding="utf-8")


def read_background_pid(pid_file: Path) -> int | None:
    """Read launcher-managed background PID if available."""
    if not pid_file.exists():
        return None
    try:
        value = pid_file.read_text(encoding="utf-8").strip()
        return int(value) if value else None
    except (ValueError, OSError):
        return None


def clear_background_pid(pid_file: Path) -> None:
    """Delete launcher-managed background PID file."""
    if pid_file.exists():
        pid_file.unlink(missing_ok=True)


def print_runtime_status(port: int, pid_file: Path, log_file: Path) -> None:
    """Print backend listener and tracked launcher PID status."""
    backend_pids = sorted(find_listener_pids(port))
    tracked_pid = read_background_pid(pid_file)
    tracked_label = "none"

    if tracked_pid:
        if tracked_pid in backend_pids or is_process_alive(tracked_pid):
            tracked_label = str(tracked_pid)
        else:
            tracked_label = f"{tracked_pid} (stale)"
            if not backend_pids:
                clear_background_pid(pid_file)
                tracked_label = f"{tracked_pid} (stale-cleared)"

    print("[status] Runtime listeners")
    print(f" - Backend ({port}): {'up' if backend_pids else 'down'}")
    if backend_pids:
        print(f"   PIDs: {', '.join(str(pid) for pid in backend_pids)}")
    print(f" - Tracked backend PID: {tracked_label}")
    print(f" - Backend log: {log_file if log_file.exists() else 'not created yet'}")


def stop_pid(pid: int) -> None:
    """Terminate a process by PID, escalating when required."""
    if pid == os.getpid() or pid <= 0:
        return

    if os.name == "nt":
        result = subprocess.run(
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

    try:
        os.kill(pid, signal.SIGKILL)
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


def stop_background_server(port: int, pid_file: Path) -> None:
    """Stop launcher-managed background server and clear stale PID state."""
    print("[1/2] Stopping background backend web server...")
    stopped = False
    found = False

    pid = read_background_pid(pid_file)
    if pid and is_process_alive(pid):
        found = True
        try:
            stop_pid(pid)
            print(f" - Stopped PID from launcher file: {pid}.")
            stopped = True
        except RuntimeError as exc:
            print(f" - Could not stop PID {pid}: {exc}")
    clear_background_pid(pid_file)

    extra_pids = find_listener_pids(port)
    for extra_pid in sorted(extra_pids):
        found = True
        try:
            stop_pid(extra_pid)
            if extra_pid in find_listener_pids(port):
                print(f" - Could not stop listener PID {extra_pid}: still listening on {port}.")
            else:
                print(f" - Stopped listener PID: {extra_pid}.")
                stopped = True
        except RuntimeError as exc:
            print(f" - Could not stop listener PID {extra_pid}: {exc}")

    if not found:
        print(" - No running server found.")
    elif not stopped:
        print(" - Server is still running. Close the owner terminal or retry with elevated permissions.")

    print("[2/2] Done.")
