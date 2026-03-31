"""Platform-specific system operations plugin."""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import shutil
from pathlib import Path

from plugins.base import Plugin

logger = logging.getLogger(__name__)

_DIALOG_TIMEOUT_SECONDS: float = 120.0
_REVEAL_TIMEOUT_SECONDS: float = 30.0
_PICKER_TITLE = "Select Download Folder"
_INITIAL_DIR_ENV_VAR = "APP_FOLDER_PICKER_INITIAL_DIR"

_PLATFORM = platform.system()


class SystemPlugin(Plugin):
    """Platform-specific system operations (dialogs, file manager)."""

    async def _run_subprocess(
        self,
        *args: str,
        timeout: float,
        env: dict[str, str] | None = None,
    ) -> tuple[int | None, str, str]:
        """Execute a subprocess with timeout and capture output.

        Returns:
            (returncode, stdout, stderr). returncode is None if there was a timeout
            or launch error.
        """
        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        except (FileNotFoundError, PermissionError) as exc:
            logger.debug("Could not launch %r: %s", args[0], exc)
            return None, "", str(exc)

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            logger.warning("Subprocess %r timed out after %.0fs.", args[0], timeout)
            return None, "", "timeout"

        stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
        return process.returncode, stdout, stderr

    @staticmethod
    def _escape_applescript_literal(value: str) -> str:
        """Escape backslashes and double quotes for an AppleScript literal."""
        return value.replace("\\", "\\\\").replace('"', '\\"')

    async def show_folder_picker(
        self, initial_dir: Path | str | None = None
    ) -> Path | None:
        """Show the native folder selection dialog.

        Returns:
            Path selected by the user, or None if cancelled or failed.
        """
        initial = str(initial_dir) if initial_dir else None

        try:
            if _PLATFORM == "Darwin":
                return await self._show_macos_picker(initial)
            if _PLATFORM == "Linux":
                return await self._show_linux_picker(initial)
            if _PLATFORM == "Windows":
                return await self._show_windows_picker(initial)
        except Exception:
            logger.exception(
                "Unexpected error in show_folder_picker (platform=%r).", _PLATFORM
            )

        logger.debug("Platform not supported for folder picker: %r.", _PLATFORM)
        return None

    async def _show_macos_picker(self, initial_dir: str | None) -> Path | None:
        if initial_dir:
            escaped = self._escape_applescript_literal(initial_dir)
            script = (
                f'POSIX path of (choose folder with prompt "{_PICKER_TITLE}" '
                f'default location POSIX file "{escaped}")'
            )
        else:
            script = f'POSIX path of (choose folder with prompt "{_PICKER_TITLE}")'

        return_code, stdout, _ = await self._run_subprocess(
            "osascript",
            "-e",
            script,
            timeout=_DIALOG_TIMEOUT_SECONDS,
        )
        if return_code == 0 and stdout.strip():
            return Path(stdout.strip())
        return None

    async def _show_linux_picker(self, initial_dir: str | None) -> Path | None:
        if shutil.which("zenity"):
            cmd = [
                "zenity",
                "--file-selection",
                "--directory",
                f"--title={_PICKER_TITLE}",
            ]
            if initial_dir:
                cmd.extend(["--filename", initial_dir.rstrip("/") + "/"])
        elif shutil.which("kdialog"):
            cmd = [
                "kdialog",
                "--getexistingdirectory",
                initial_dir or ".",
                "--title",
                _PICKER_TITLE,
            ]
        else:
            logger.debug(
                "Neither zenity nor kdialog found for the folder picker on Linux."
            )
            return None

        return_code, stdout, _ = await self._run_subprocess(
            *cmd, timeout=_DIALOG_TIMEOUT_SECONDS
        )
        if return_code == 0 and stdout.strip():
            return Path(stdout.strip())
        return None

    async def _show_windows_picker(self, initial_dir: str | None) -> Path | None:
        ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = "{_PICKER_TITLE}"
$dialog.ShowNewFolderButton = $true
$initialDir = $env:{_INITIAL_DIR_ENV_VAR}
if ($initialDir -and (Test-Path -LiteralPath $initialDir)) {{
    $dialog.SelectedPath = $initialDir
}}
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
    Write-Output $dialog.SelectedPath
}}
"""
        env = os.environ.copy()
        if initial_dir:
            env[_INITIAL_DIR_ENV_VAR] = initial_dir

        return_code, stdout, _ = await self._run_subprocess(
            "powershell",
            "-Command",
            ps_script,
            timeout=_DIALOG_TIMEOUT_SECONDS,
            env=env,
        )
        if return_code == 0 and stdout.strip():
            return Path(stdout.strip())
        return None

    async def reveal_in_file_manager(self, path: Path | str) -> bool:
        """Open the file manager and select the indicated file.

        Returns:
            True if the command was launched successfully, False otherwise.
        """
        resolved = Path(path).resolve()
        if not resolved.exists():
            logger.warning("reveal_in_file_manager: path does not exist: %s", resolved)
            return False

        try:
            if _PLATFORM == "Darwin":
                rc, _, _ = await self._run_subprocess(
                    "open",
                    "-R",
                    str(resolved),
                    timeout=_REVEAL_TIMEOUT_SECONDS,
                )
            elif _PLATFORM == "Windows":
                rc, _, _ = await self._run_subprocess(
                    "explorer",
                    f"/select,{resolved}",
                    timeout=_REVEAL_TIMEOUT_SECONDS,
                )
            else:
                target = resolved.parent if resolved.is_file() else resolved
                rc, _, _ = await self._run_subprocess(
                    "xdg-open",
                    str(target),
                    timeout=_REVEAL_TIMEOUT_SECONDS,
                )
        except Exception:
            logger.exception("Unexpected error in reveal_in_file_manager: %s", resolved)
            return False

        return rc == 0
