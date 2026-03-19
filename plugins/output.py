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
    """Manage output directories and generated file structure."""

    def get_default_dir(self) -> Path:
        """Return the default output directory from config."""
        return config.OUTPUT_DIR

    def validate_dir(self, path: str | Path) -> tuple[bool, str, Path | None]:
        """Validate that a directory exists and is writable."""
        resolved = Path(path)

        if not resolved.exists():
            try:
                resolved.mkdir(parents=True, exist_ok=True)
                logger.debug("Directory created: %s", resolved)
            except Exception as exc:
                logger.warning("Could not create directory %s: %s", resolved, exc)
                return False, f"Cannot create directory: {exc}", None

        if not resolved.is_dir():
            return False, f"Path is not a directory: {resolved}", None

        try:
            test_file = resolved / ".write_test"
            test_file.touch()
            test_file.unlink()
        except Exception as exc:
            logger.warning("Directory is not writable %s: %s", resolved, exc)
            return False, "Directory is not writable", None

        return True, "Directory is valid", resolved

    def create_book_dir(
        self,
        output_dir: Path,
        book_id: str,
        title: str,
        authors: list[str] | None = None,
    ) -> Path:
        """Create a unique output directory for a single download job."""
        output_dir.mkdir(parents=True, exist_ok=True)

        folder_name = self._build_folder_name(book_id, title, authors)
        book_dir = self._create_unique_book_dir(
            output_dir=output_dir,
            folder_name=folder_name,
            book_id=book_id,
        )

        oebps = book_dir / _OEBPS
        oebps.mkdir(parents=True, exist_ok=False)
        logger.debug("Book directory prepared: %s", book_dir)

        meta_file = book_dir / _BOOK_ID_FILE
        meta_file.write_text(book_id, encoding="utf-8")

        return book_dir

    def _build_folder_name(
        self,
        book_id: str,
        title: str,
        authors: list[str] | None,
    ) -> str:
        """Build a slugified folder name for the book."""
        folder_title = (title or "").strip()
        if not folder_title and authors:
            valid_authors = [str(a).strip() for a in authors if a and str(a).strip()]
            if valid_authors:
                folder_title = f"Book by {valid_authors[0]}"
        if not folder_title:
            folder_title = book_id
        return slugify(folder_title)

    def _create_unique_book_dir(
        self,
        *,
        output_dir: Path,
        folder_name: str,
        book_id: str,
    ) -> Path:
        """Atomically reserve a unique directory path to avoid race conditions."""
        base_candidate = output_dir / folder_name
        for suffix in range(0, 1000):
            candidate = (
                base_candidate
                if suffix == 0
                else output_dir / f"{folder_name}-{suffix + 1}"
            )
            try:
                candidate.mkdir(parents=False, exist_ok=False)
                return candidate
            except FileExistsError:
                continue

        fallback_base = slugify(f"{folder_name}-{book_id}") or "book"
        for suffix in range(1001, 2001):
            fallback = output_dir / f"{fallback_base}-{suffix}"
            try:
                fallback.mkdir(parents=False, exist_ok=False)
                logger.warning(
                    "No free variant found for %s after 1000 attempts; using %s.",
                    base_candidate,
                    fallback,
                )
                return fallback
            except FileExistsError:
                continue

        raise RuntimeError(f"Could not allocate output directory for {book_id!r}")

    def get_oebps_dir(self, book_dir: Path) -> Path:
        """Return the OEBPS directory for a book."""
        return book_dir / _OEBPS

    def get_images_dir(self, book_dir: Path) -> Path:
        """Return the images directory for a book."""
        return book_dir / _OEBPS / _IMAGES

    def get_styles_dir(self, book_dir: Path) -> Path:
        """Return the styles directory for a book."""
        return book_dir / _OEBPS / _STYLES
