"""Output directory management plugin."""

from __future__ import annotations

import logging
from pathlib import Path

import config
from plugins.base import Plugin
from utils import slugify

logger = logging.getLogger(__name__)

_OEBPS = "OEBPS"
_IMAGES = "Images"
_STYLES = "Styles"
_BOOK_ID_FILE = ".book_id"


class OutputPlugin(Plugin):
    """Gestiona directorios de salida y organización de archivos."""

    def get_default_dir(self) -> Path:
        """Retorna el directorio de salida por defecto según config."""
        return config.OUTPUT_DIR

    def validate_dir(self, path: str | Path) -> tuple[bool, str, Path | None]:
        """Valida que un directorio existe y tiene permisos de escritura.

        Intenta crear el directorio si no existe.

        Returns:
            (True, mensaje, path) si es válido.
            (False, mensaje_de_error, None) si no es válido.
        """
        resolved = Path(path)

        if not resolved.exists():
            try:
                resolved.mkdir(parents=True, exist_ok=True)
                logger.debug("Directorio creado: %s", resolved)
            except Exception as exc:
                logger.warning("No se pudo crear el directorio %s: %s", resolved, exc)
                return False, f"Cannot create directory: {exc}", None

        if not resolved.is_dir():
            return False, f"Path is not a directory: {resolved}", None

        try:
            test_file = resolved / ".write_test"
            test_file.touch()
            test_file.unlink()
        except Exception as exc:
            logger.warning("Directorio sin permisos de escritura %s: %s", resolved, exc)
            return False, "Directory is not writable", None

        return True, "Directory is valid", resolved

    def create_book_dir(
        self,
        output_dir: Path,
        book_id: str,
        title: str,
        authors: list[str] | None = None,
    ) -> Path:
        """Crea el directorio de salida para un libro con resolución de conflictos.

        La estructura creada es::

            output_dir/
            └── {slug}/
                ├── OEBPS/
                └── .book_id

        Returns:
            Ruta al directorio del libro (creado o existente).
        """
        folder_name = self._build_folder_name(book_id, title, authors)
        book_dir = self._resolve_conflict(output_dir / folder_name, book_id)

        oebps = book_dir / _OEBPS
        oebps.mkdir(parents=True, exist_ok=True)
        logger.debug("Directorio de libro preparado: %s", book_dir)

        meta_file = book_dir / _BOOK_ID_FILE
        if (
            not meta_file.exists()
            or meta_file.read_text(encoding="utf-8").strip() != book_id
        ):
            meta_file.write_text(book_id, encoding="utf-8")

        return book_dir

    def _build_folder_name(
        self,
        book_id: str,
        title: str,
        authors: list[str] | None,
    ) -> str:
        """Construye el nombre de carpeta slugificado para el libro."""
        folder_title = (title or "").strip()
        if not folder_title and authors:
            valid_authors = [str(a).strip() for a in authors if a and str(a).strip()]
            if valid_authors:
                folder_title = f"Book by {valid_authors[0]}"
        if not folder_title:
            folder_title = book_id
        return slugify(folder_title)

    def _resolve_conflict(self, book_dir: Path, book_id: str) -> Path:
        """Resuelve conflictos de nombre cuando dos libros distintos tienen el mismo slug.

        Si el directorio existe con un ID diferente, intenta variantes con sufijo
        hasta encontrar una libre o que ya pertenezca al mismo libro.
        """
        meta_file = book_dir / _BOOK_ID_FILE

        if not book_dir.exists():
            return book_dir

        if meta_file.exists():
            existing_id = meta_file.read_text(encoding="utf-8").strip()
            if existing_id == book_id:
                return book_dir

        base = book_dir
        for suffix in range(2, 100):
            candidate = base.parent / f"{base.name}-{suffix}"
            candidate_meta = candidate / _BOOK_ID_FILE
            if not candidate.exists():
                logger.debug(
                    "Conflicto de directorio resuelto: %s → %s", book_dir, candidate
                )
                return candidate
            if candidate_meta.exists():
                candidate_id = candidate_meta.read_text(encoding="utf-8").strip()
                if candidate_id == book_id:
                    return candidate

        fallback = base.parent / f"{base.name}-{book_id}"
        logger.warning(
            "No se encontró variante libre para %s tras 100 intentos; usando %s.",
            book_dir,
            fallback,
        )
        return fallback

    def get_oebps_dir(self, book_dir: Path) -> Path:
        """Retorna el directorio OEBPS del libro."""
        return book_dir / _OEBPS

    def get_images_dir(self, book_dir: Path) -> Path:
        """Retorna el directorio de imágenes del libro."""
        return book_dir / _OEBPS / _IMAGES

    def get_styles_dir(self, book_dir: Path) -> Path:
        """Retorna el directorio de hojas de estilo del libro."""
        return book_dir / _OEBPS / _STYLES
