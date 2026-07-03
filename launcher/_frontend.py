"""Frontend (Astro/React) build helpers using bun and Node."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import TYPE_CHECKING

import config
from launcher._runtime import REPO_ROOT, run_checked

if TYPE_CHECKING:
    from pathlib import Path

    from launcher._steps import Steps

TIMEOUT_BUN_SECONDS: int = int(os.getenv("RYLIOX_TIMEOUT_BUN", "300"))
ASTRO_FALLBACK_NODE_VERSION: str = (
    getattr(config.SETTINGS, "astro_fallback_node_version", None) or "22.20.0"
)

WATCH_EXTENSIONS: frozenset[str] = frozenset(
    {".astro", ".tsx", ".ts", ".jsx", ".js", ".css", ".json"}
)
WATCH_PATHS: tuple[str, ...] = (
    "src",
    "astro.config.mjs",
    "tailwind.config.mjs",
    "postcss.config.js",
    "package.json",
)
EXCLUDED_DIRS: frozenset[str] = frozenset({"node_modules", ".git", ".github", ".vscode", "dist"})


def require_bun() -> str:
    bun = shutil.which("bun")
    if not bun:
        raise RuntimeError(
            "bun not found in PATH. Install it to manage frontend dependencies and builds."
        )
    return bun


def parse_node_version(output: str) -> tuple[int, int, int] | None:
    raw = output.strip().lstrip("v")
    parts = raw.split(".")
    if not 1 <= len(parts) <= 3:
        return None
    try:
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return major, minor, patch
    except (ValueError, IndexError):
        return None


def current_node_version() -> tuple[int, int, int] | None:
    node = shutil.which("node")
    if not node:
        return None
    try:
        result = subprocess.run(
            [node, "--version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except subprocess.CalledProcessError as exc:
        print(f"  [WARN] Node version check failed: exit code {exc.returncode}")
        return None
    except subprocess.TimeoutExpired:
        print("  [WARN] Node version check timed out")
        return None
    except FileNotFoundError:
        return None
    return parse_node_version(result.stdout)


def is_supported_astro_node(version: tuple[int, int, int] | None) -> bool:
    if version is None:
        return False
    major, minor, patch = version
    if major < 22:
        return False
    if major == 22 and (minor, patch) < (12, 0):
        return False
    return major % 2 == 0


def build_command(bun: str) -> list[str]:
    version = current_node_version()
    if is_supported_astro_node(version):
        return [bun, "run", "build"]

    npx = shutil.which("npx")
    astro_entry = REPO_ROOT / "frontend" / "node_modules" / "astro" / "astro.js"
    if npx and astro_entry.exists():
        print(
            " - Bun is available but the detected Node version is not compatible; using "
            f"Node {ASTRO_FALLBACK_NODE_VERSION} via npx to build frontend..."
        )
        return [
            npx,
            "-y",
            f"node@{ASTRO_FALLBACK_NODE_VERSION}",
            str(astro_entry),
            "build",
        ]

    found = f"v{version[0]}.{version[1]}.{version[2]}" if version else "unknown"
    raise RuntimeError(
        "Astro 7 requires an even Node.js version >= 22.12.0. "
        f"Detected version: {found}. Install Node 22/24 or ensure npx is available."
    )


def _source_newer_than_build(frontend_dir: Path, dist_dir: Path) -> bool:
    build_index = dist_dir / "index.html"
    if not build_index.exists():
        return True
    try:
        build_mtime = build_index.stat().st_mtime
    except OSError:
        return True

    for rel in WATCH_PATHS:
        candidate = frontend_dir / rel
        if not candidate.exists():
            continue
        paths: list[Path] = [candidate] if candidate.is_file() else list(candidate.rglob("*"))
        for path in paths:
            if any(excluded in path.parts for excluded in EXCLUDED_DIRS):
                continue
            if path.is_file() and path.suffix in WATCH_EXTENSIONS:
                try:
                    if path.stat().st_mtime > build_mtime:
                        return True
                except OSError as exc:
                    print(f"   [WARN] Could not check mtime for {path}: {exc}")
    return False


def ensure_dependencies(bun: str, frontend_dir: Path, steps: Steps) -> None:
    if (frontend_dir / "node_modules").exists():
        steps.next("Frontend dependencies already installed.")
        return
    lockfile = frontend_dir / "bun.lock"
    cmd: list[str] = [bun, "install"]
    if lockfile.exists():
        cmd.append("--frozen-lockfile")
        print("   Lockfile found: using frozen install")
    else:
        print("   No lockfile found: using standard install")
    run_checked(
        cmd,
        steps.format("Installing frontend dependencies..."),
        cwd=frontend_dir,
        timeout=TIMEOUT_BUN_SECONDS,
    )


def ensure_build(steps: Steps, rebuild: bool = False) -> None:
    frontend_dir = REPO_ROOT / "frontend"
    if not frontend_dir.exists():
        raise RuntimeError("frontend/ directory not found.")

    dist_dir = frontend_dir / "dist"
    needs = rebuild or not dist_dir.exists() or _source_newer_than_build(frontend_dir, dist_dir)

    if not needs:
        steps.next("Frontend build already available.")
        return

    bun = require_bun()
    ensure_dependencies(bun, frontend_dir, steps)
    label = (
        "Sources modified, rebuilding bundle..."
        if dist_dir.exists()
        else "Building frontend bundle..."
    )
    try:
        run_checked(
            build_command(bun),
            steps.format(label),
            cwd=frontend_dir,
            timeout=TIMEOUT_BUN_SECONDS,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr.decode("utf-8", errors="replace") if exc.stderr else "")[:1000]
        raise RuntimeError(
            f"Frontend build failed. Check Node/Astro errors and try again.\nBuild stderr: {stderr}"
        ) from exc
