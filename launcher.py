"""Local runtime launcher."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Callable

from core import process_manager
from web.dependencies import DOWNLOAD_ERROR_LOG_DIR, DOWNLOAD_QUEUE_DB

REPO_ROOT = Path(__file__).resolve().parent

PORT: int = int(os.getenv("PORT", "8000"))
URL: str = f"http://localhost:{PORT}"

RUN_DIR = REPO_ROOT / ".run"
PID_FILE = RUN_DIR / "web-server.pid"
LOG_FILE = RUN_DIR / "web-server.log"

_TIMEOUT_PIP = 300
_TIMEOUT_NPM = 300
_TIMEOUT_DOCKER = 120
_TIMEOUT_SUBPROCESS = 60




class Steps:
    """Contador de pasos para mensajes de progreso.

    En vez de requerir un total exacto en el constructor, acepta un total
    estimado y muestra '?' si se supera, evitando [3/6] incorrectos en
    caminos rápidos donde no todos los pasos se ejecutan.
    """

    def __init__(self, total: int) -> None:
        self._total = total
        self._current = 0

    def next(self, label: str) -> None:
        """Imprime el siguiente paso inmediatamente."""
        self._current += 1
        total_str = str(self._total) if self._current <= self._total else "?"
        print(f"[{self._current}/{total_str}] {label}")

    def format(self, label: str) -> str:
        """Formatea el label con prefijo numerado sin imprimirlo.

        Llama a esto justo antes de pasar el mensaje a _run_checked para
        que el número se incremente en el momento correcto.
        """
        self._current += 1
        total_str = str(self._total) if self._current <= self._total else "?"
        return f"[{self._current}/{total_str}] {label}"




def _print_title() -> None:
    print()
    print("==========================================")
    print(" Ryliox Launcher")
    print("==========================================")
    print()


def _run_checked(
    command: list[str],
    step: str,
    cwd: Path | None = None,
    timeout: int | None = None,
) -> None:
    """Imprime el paso y ejecuta el comando. Lanza CalledProcessError si falla."""
    print(step)
    try:
        subprocess.run(command, cwd=cwd or REPO_ROOT, check=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Comando agotó el timeout de {timeout}s: {' '.join(command[:2])}"
        ) from exc


def _open_browser(delay: float = 1.5) -> None:
    time.sleep(delay)
    try:
        webbrowser.open(URL)
    except Exception as exc:
        print(f"  [WARN] No se pudo abrir el navegador: {exc}")


def _open_browser_async(delay: float = 1.5) -> None:
    threading.Thread(target=_open_browser, args=(delay,), daemon=True).start()




def _venv_python() -> Path:
    subpath = r".venv\Scripts\python.exe" if os.name == "nt" else ".venv/bin/python"
    return REPO_ROOT / subpath


def _server_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    venv_dir = REPO_ROOT / ".venv"
    venv_bin = venv_dir / ("Scripts" if os.name == "nt" else "bin")
    if env.get("VIRTUAL_ENV") != str(venv_dir):
        env["VIRTUAL_ENV"] = str(venv_dir)
    path = env.get("PATH", "")
    venv_bin_str = str(venv_bin)
    if venv_bin_str not in path:
        env["PATH"] = f"{venv_bin_str}{os.pathsep}{path}" if path else venv_bin_str
    return env


def _venv_has_runtime_dependencies(venv_python: Path) -> bool:
    """Verifica dependencias importando los paquetes clave del requirements.txt.

    La lista está aquí y no en requirements.txt directamente para evitar
    parsear el archivo (que puede tener extras, versiones, comentarios).
    Actualizar esta lista cuando cambie requirements.txt.
    """
    result = subprocess.run(
        [
            str(venv_python),
            "-c",
            "import fastapi, uvicorn, bleach, lxml, httpx, pydantic_settings, fake_useragent",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        timeout=10,
    )
    return result.returncode == 0


def _ensure_python_runtime(steps: Steps) -> Path:
    venv_dir = REPO_ROOT / ".venv"
    venv_python = _venv_python()

    if not venv_python.exists():
        steps.next("Creando entorno virtual .venv...")
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            cwd=REPO_ROOT,
            check=True,
            timeout=_TIMEOUT_SUBPROCESS,
        )
    else:
        steps.next("Entorno virtual encontrado.")

    if _venv_has_runtime_dependencies(venv_python):
        steps.next("Dependencias Python ya instaladas.")
    else:
        _run_checked(
            [
                str(venv_python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                "-r",
                "requirements.txt",
            ],
            steps.format("Instalando/actualizando dependencias Python..."),
            timeout=_TIMEOUT_PIP,
        )
    return venv_python




def _clean_runtime_cache() -> None:
    """Elimina cache de cola y logs de error. No toca datos de usuario."""
    print(" - Limpiando cache de runtime...")
    cleaned: list[str] = []

    for path in [DOWNLOAD_QUEUE_DB]:
        try:
            if path.exists():
                path.unlink()
                cleaned.append(path.name)
        except OSError as exc:
            print(f"   [WARN] No se pudo borrar {path.name}: {exc}")

    if DOWNLOAD_ERROR_LOG_DIR.exists():
        for log_file in DOWNLOAD_ERROR_LOG_DIR.glob("download-error-*.log"):
            try:
                log_file.unlink()
                cleaned.append(log_file.name)
            except OSError as exc:
                print(f"   [WARN] No se pudo borrar {log_file.name}: {exc}")

    if cleaned:
        print(f"   Borrados: {', '.join(cleaned)}")
    else:
        print("   Nada que limpiar.")



_FRONTEND_WATCH_EXTENSIONS = {".astro", ".tsx", ".ts", ".jsx", ".js", ".css", ".json"}
_FRONTEND_WATCH_PATHS = [
    "src",
    "astro.config.mjs",
    "tailwind.config.mjs",
    "postcss.config.js",
    "package.json",
]


def _require_npm() -> str:
    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("npm no encontrado en PATH. Instala Node.js primero.")
    return npm


def _frontend_source_newer_than_build(frontend_dir: Path, dist_dir: Path) -> bool:
    """Retorna True si algún fuente es más nuevo que dist/index.html."""
    build_index = dist_dir / "index.html"
    if not build_index.exists():
        return True
    try:
        build_mtime = build_index.stat().st_mtime
    except OSError:
        return True

    for rel_path in _FRONTEND_WATCH_PATHS:
        candidate = frontend_dir / rel_path
        if not candidate.exists():
            continue
        paths: list[Path] = (
            [candidate] if candidate.is_file() else list(candidate.rglob("*"))
        )
        for path in paths:
            if path.is_file() and path.suffix in _FRONTEND_WATCH_EXTENSIONS:
                try:
                    if path.stat().st_mtime > build_mtime:
                        return True
                except OSError:
                    continue
    return False


def _ensure_frontend_dependencies(npm: str, frontend_dir: Path, steps: Steps) -> None:
    if (frontend_dir / "node_modules").exists():
        steps.next("Dependencias frontend ya instaladas.")
        return
    lockfile = frontend_dir / "package-lock.json"
    cmd = [npm, "ci" if lockfile.exists() else "install", "--no-audit", "--no-fund"]
    _run_checked(
        cmd,
        steps.format("Instalando dependencias frontend..."),
        cwd=frontend_dir,
        timeout=_TIMEOUT_NPM,
    )


def _ensure_frontend_build(steps: Steps, rebuild: bool = False) -> None:
    frontend_dir = REPO_ROOT / "frontend"
    if not frontend_dir.exists():
        raise RuntimeError("Directorio frontend/ no encontrado.")

    dist_dir = frontend_dir / "dist"
    needs_rebuild = (
        rebuild
        or not dist_dir.exists()
        or _frontend_source_newer_than_build(frontend_dir, dist_dir)
    )

    if not needs_rebuild:
        steps.next("Build del frontend ya disponible.")
        return

    npm = _require_npm()
    _ensure_frontend_dependencies(npm, frontend_dir, steps)
    label = (
        "Fuentes modificadas, reconstruyendo bundle..."
        if dist_dir.exists()
        else "Construyendo bundle frontend..."
    )
    try:
        _run_checked(
            [npm, "run", "build"],
            steps.format(label),
            cwd=frontend_dir,
            timeout=_TIMEOUT_NPM,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "Build del frontend falló. Revisa los errores de Node/Astro y vuelve a intentar."
        ) from exc




def _ensure_run_dir() -> None:
    """Crea .run/ si no existe (necesario para PID_FILE y LOG_FILE)."""
    RUN_DIR.mkdir(exist_ok=True)


def _stop_port(steps: Steps) -> None:
    process_manager.stop_port(
        PORT, step_label=steps.format(f"Liberando localhost:{PORT}...")
    )


def _launch_server(
    venv_python: Path,
    steps: Steps,
    label: str = "Iniciando servidor web...",
) -> None:
    """Lanza el servidor en primer plano. Bloquea hasta que el proceso termina."""
    steps.next(label)
    subprocess.run(
        [str(venv_python), "-X", "utf8", "-m", "web.server"],
        cwd=REPO_ROOT,
        env=_server_env(),
        check=True,
    )




def _detect_compose_command() -> tuple[list[str], bool]:
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker no está instalado o no está disponible en PATH.")
    if (
        subprocess.run(
            [docker, "compose", "version"],
            capture_output=True,
            check=False,
            timeout=10,
        ).returncode
        == 0
    ):
        return [docker, "compose"], True
    compose = shutil.which("docker-compose")
    if compose:
        return [compose], False
    raise RuntimeError("No se encontró el plugin Docker Compose ni docker-compose.")


def _verify_docker_containers_running(compose: list[str]) -> None:
    """Verifica que los contenedores hayan arrancado tras `up -d`."""
    result = subprocess.run(
        compose + ["ps", "--services", "--filter", "status=running"],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    if result.returncode != 0 or not result.stdout.strip():
        print(
            "  [WARN] No se pudieron verificar los contenedores. "
            f"Comprueba con: {' '.join(compose)} ps"
        )




def run_status() -> None:
    process_manager.print_runtime_status(
        port=PORT, pid_file=PID_FILE, log_file=LOG_FILE
    )


def run_stop() -> None:
    process_manager.stop_background_server(port=PORT, pid_file=PID_FILE)


def run_backend_only(open_browser: bool = True) -> None:
    _print_title()
    _ensure_run_dir()
    steps = Steps(total=4)
    _stop_port(steps)
    steps.next("Modo: solo backend")
    venv_python = _ensure_python_runtime(steps)
    _clean_runtime_cache()
    if open_browser:
        _open_browser_async()
    _launch_server(venv_python, steps, label=f"Iniciando API en {URL}...")


def run_unified(open_browser: bool = True, rebuild_frontend: bool = False) -> None:
    _print_title()
    _ensure_run_dir()
    steps = Steps(total=6)
    _stop_port(steps)
    steps.next("Modo: unificado")
    venv_python = _ensure_python_runtime(steps)
    _ensure_frontend_build(steps, rebuild=rebuild_frontend)
    _clean_runtime_cache()
    if open_browser:
        _open_browser_async()
    _launch_server(
        venv_python, steps, label=f"Iniciando servidor unificado en {URL}..."
    )


def run_docker(open_browser: bool = True) -> None:
    _print_title()
    _ensure_run_dir()
    steps = Steps(total=4)
    _stop_port(steps)
    steps.next("Modo: Docker Compose")

    compose_file = REPO_ROOT / "docker-compose.yml"
    if not compose_file.exists():
        raise RuntimeError("docker-compose.yml no encontrado.")

    compose, is_plugin = _detect_compose_command()
    quiet_flag = "--quiet" if is_plugin else "-q"
    _run_checked(
        compose + ["-f", str(compose_file), "config", quiet_flag],
        steps.format("Validando configuración compose..."),
        timeout=_TIMEOUT_SUBPROCESS,
    )
    _run_checked(
        compose + ["up", "-d"],
        steps.format("Iniciando contenedores..."),
        timeout=_TIMEOUT_DOCKER,
    )
    _verify_docker_containers_running(compose)

    if open_browser:
        _open_browser_async()
    print(f"\nServidor disponible en {URL}")



_MODES: dict[str, str] = {
    "1": "unified",
    "2": "stop",
    "3": "status",
    "4": "docker",
    "q": "quit",
}

_MODE_LABELS: dict[str, str] = {
    "unified": "1) Aplicación unificada en :8000 (recomendado)",
    "stop": "2) Detener servicios en ejecución",
    "status": "3) Mostrar estado del runtime",
    "docker": "4) Modo Docker",
}


def _interactive_mode() -> str:
    """Muestra menú interactivo. Retorna 'unified' si stdin no es TTY (CI/pipe)."""
    if not sys.stdin.isatty():
        print("  (stdin no es TTY, modo por defecto: unified)")
        return "unified"
    print("Selecciona modo:")
    for label in _MODE_LABELS.values():
        print(f"  {label}")
    print("  q) Salir")
    choice = input("Opción [1]: ").strip().lower() or "1"
    mode = _MODES.get(choice)
    if mode is None:
        print(
            f"  [WARN] Opción '{choice}' no reconocida, usando modo por defecto: unified"
        )
        return "unified"
    return mode


def _parse_cli_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m launcher")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--stop", action="store_true")
    mode.add_argument("--docker", action="store_true")
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--backend-only", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--rebuild-frontend", action="store_true")
    return parser.parse_args(argv)


def _resolve_mode(argv: list[str], args: argparse.Namespace) -> str:
    """Determina el modo. Si no hay args, muestra menú interactivo."""
    if not argv:
        return _interactive_mode()
    if args.status:
        return "status"
    if args.stop:
        return "stop"
    if args.docker:
        return "docker"
    if args.backend_only:
        return "backend_only"
    return "unified"


def main() -> int:
    try:
        os.chdir(REPO_ROOT)
        argv = sys.argv[1:]
        args = _parse_cli_args(argv)

        if not argv:
            _print_title()

        open_browser = not args.no_browser
        mode = _resolve_mode(argv, args)

        dispatch: dict[str, Callable[[], None]] = {
            "quit": lambda: None,
            "status": run_status,
            "stop": run_stop,
            "docker": lambda: run_docker(open_browser),
            "backend_only": lambda: run_backend_only(open_browser),
            "unified": lambda: run_unified(open_browser, args.rebuild_frontend),
        }

        if mode == "quit":
            return 0

        action = dispatch.get(mode)
        if action is None:
            raise ValueError(f"Modo desconocido: {mode!r}")
        action()
        return 0

    except KeyboardInterrupt:
        print("\nCancelado por el usuario.")
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"\nERROR: Comando terminó con código {exc.returncode}.")
        return 1
    except RuntimeError as exc:
        print(f"\nERROR: {exc}")
        return 1
    except Exception as exc:
        print(f"\nERROR INESPERADO ({type(exc).__name__}): {exc}")
        print("Por favor reporta este error incluyendo el traceback completo.")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
