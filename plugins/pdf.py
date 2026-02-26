"""PDF generation plugin using WeasyPrint."""

from __future__ import annotations

import html
import logging
import posixpath
import re
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

from utils.files import sanitize_filename

from .base import Plugin

logger = logging.getLogger(__name__)

def _get_weasyprint():
    try:
        import weasyprint

        return weasyprint
    except Exception as exc:
        raise RuntimeError(
            "WeasyPrint es necesario para generar PDFs.\n"
            "Instalar con: pip install weasyprint\n"
            "Dependencias del sistema (macOS): brew install pango\n"
            "Dependencias del sistema (Ubuntu): apt install libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0\n"
            "Dependencias del sistema (Windows): instalar GTK runtime (contiene libgobject-2.0-0)."
        ) from exc


def _get_beautifulsoup():
    """Retorna (BeautifulSoup, disponible). No lanza excepción si bs4 no está."""
    try:
        from bs4 import BeautifulSoup

        return BeautifulSoup, True
    except ImportError:
        logger.warning(
            "beautifulsoup4/lxml no están instalados. "
            "El parsing de capítulos usará regex como fallback (menos preciso)."
        )
        return None, False

_BeautifulSoup, _BS4_AVAILABLE = _get_beautifulsoup()

def generate_pdf_in_subprocess(
    book_info: dict,
    chapters: list[dict],
    toc: list[dict],
    output_dir: str,
    css_files: list[str],
    cover_image: str | None = None,
) -> str:
    """Genera un único PDF en subproceso y retorna la ruta serializable.

    Diseñada para ser llamada vía ``asyncio.to_thread`` o ``ProcessPoolExecutor``.
    No requiere kernel activo; opera directamente sobre el sistema de archivos.
    """
    pdf_path = PdfPlugin().generate(
        book_info=book_info,
        chapters=chapters,
        toc=toc,
        output_dir=Path(output_dir),
        css_files=css_files,
        cover_image=cover_image,
    )
    return str(pdf_path)


def generate_pdf_chapters_in_subprocess(
    book_info: dict,
    chapters: list[dict],
    output_dir: str,
    css_files: list[str],
) -> list[str]:
    """Genera PDFs por capítulo en subproceso y retorna rutas serializables.

    Diseñada para ser llamada vía ``asyncio.to_thread`` o ``ProcessPoolExecutor``.
    """
    pdf_paths = PdfPlugin().generate_chapters(
        book_info=book_info,
        chapters=chapters,
        output_dir=Path(output_dir),
        css_files=css_files,
    )
    return [str(p) for p in pdf_paths]

class PdfPlugin(Plugin):
    """Genera PDFs a partir del contenido descargado de un libro usando WeasyPrint."""

    def generate(
        self,
        book_info: dict,
        chapters: list[dict],
        toc: list[dict],
        output_dir: Path,
        css_files: list[str],
        cover_image: str | None = None,
    ) -> Path:
        """Genera un único PDF con todos los capítulos.

        Args:
            book_info:    Metadatos del libro (title, authors, isbn, publisher).
            chapters:     Lista de dicts de capítulo con filename, title, order.
            toc:          Estructura anidada de tabla de contenidos.
            output_dir:   Ruta al directorio output/{book_id}/.
            css_files:    Nombres de archivos CSS en OEBPS/Styles/.
            cover_image:  Nombre del archivo de portada en OEBPS/Images/ (opcional).

        Returns:
            Ruta al PDF generado.
        """
        weasyprint = _get_weasyprint()
        output_dir = Path(output_dir)
        oebps = output_dir / "OEBPS"

        logger.info(
            "Generando PDF combinado para %r en %s.", book_info.get("title"), output_dir
        )

        chapter_entries = self._collect_chapter_entries(oebps, chapters)
        if not chapter_entries:
            raise ValueError("No se encontraron capítulos válidos para generar el PDF.")

        chapter_anchor_by_href = {e["href"]: e["anchor_id"] for e in chapter_entries}
        fragment_anchor_by_key = {
            f"{e['href']}#{frag}": anchor
            for e in chapter_entries
            for frag, anchor in e.get("fragment_anchor_by_fragment", {}).items()
            if e.get("href") and frag and anchor
        }

        html_content = self._build_combined_html(
            book_info=book_info,
            chapter_entries=chapter_entries,
            toc=toc,
            oebps=oebps,
            css_files=css_files,
            cover_image=cover_image,
            chapter_anchor_by_href=chapter_anchor_by_href,
            fragment_anchor_by_key=fragment_anchor_by_key,
        )

        safe_title = self._safe_filename_stem(
            book_info.get("title"),
            book_info.get("id"),
            book_info.get("isbn"),
            fallback="book",
        )
        pdf_path = output_dir / f"{safe_title}.pdf"

        weasyprint.HTML(string=html_content, base_url=str(oebps)).write_pdf(
            str(pdf_path)
        )
        logger.info("PDF combinado generado: %s", pdf_path)
        return pdf_path

    def generate_chapters(
        self,
        book_info: dict,
        chapters: list[dict],
        output_dir: Path,
        css_files: list[str],
    ) -> list[Path]:
        """Genera un PDF individual por capítulo.

        Args:
            book_info:  Metadatos del libro.
            chapters:   Lista de dicts de capítulo con filename, title, order.
            output_dir: Ruta al directorio output/{book_id}/.
            css_files:  Nombres de archivos CSS en OEBPS/Styles/.

        Returns:
            Lista de rutas a los PDFs generados (en orden).
        """
        weasyprint = _get_weasyprint()
        output_dir = Path(output_dir)
        oebps = output_dir / "OEBPS"
        pdf_dir = output_dir / "PDF"
        pdf_dir.mkdir(exist_ok=True)

        print_css = self._get_print_css()
        original_css = self._load_css_files(oebps, css_files)

        chapter_entries = self._collect_chapter_entries(oebps, chapters)
        logger.info(
            "Generando %d PDFs de capítulos para %r.",
            len(chapter_entries),
            book_info.get("title"),
        )

        pdf_paths = []
        for index, entry in enumerate(chapter_entries, start=1):
            chapter_title_escaped = self._escape_html(
                entry.get("title") or f"Chapter {index}"
            )
            chapter_html = (
                "<!DOCTYPE html>\n<html>\n<head>\n"
                f'    <meta charset="utf-8">\n'
                f"    <title>{chapter_title_escaped}</title>\n"
                f"    <style>{print_css}</style>\n"
                f"    <style>{original_css}</style>\n"
                "</head>\n<body>\n"
                '    <section class="chapter">\n'
                f'        <h1 class="chapter-title">{chapter_title_escaped}</h1>\n'
                f'        {entry["body"]}\n'
                "    </section>\n</body>\n</html>"
            )

            safe_stem = self._safe_filename_stem(
                entry.get("title"),
                entry.get("href"),
                fallback=f"chapter_{index}",
            )
            pdf_path = pdf_dir / f"{index:03d}_{safe_stem}.pdf"
            weasyprint.HTML(string=chapter_html, base_url=str(oebps)).write_pdf(
                str(pdf_path)
            )
            pdf_paths.append(pdf_path)
            logger.debug(
                "Capítulo %d/%d generado: %s", index, len(chapter_entries), pdf_path
            )

        return pdf_paths

    def _build_combined_html(
        self,
        book_info: dict,
        chapter_entries: list[dict],
        toc: list[dict],
        oebps: Path,
        css_files: list[str],
        cover_image: str | None,
        chapter_anchor_by_href: dict[str, str],
        fragment_anchor_by_key: dict[str, str],
    ) -> str:
        print_css = self._get_print_css()
        original_css = self._load_css_files(oebps, css_files)
        cover_image_name = self._resolve_cover_image(oebps, cover_image)
        cover_html = self._generate_cover_html(book_info, cover_image_name)
        toc_html = self._generate_toc_html(
            toc,
            chapter_entries,
            chapter_anchor_by_href,
            fragment_anchor_by_key,
        )

        chapters_html = "\n".join(
            f'<section class="{"chapter chapter-first" if i == 0 else "chapter"}" '
            f'id="{entry["anchor_id"]}">\n'
            f'    <h1 class="chapter-title">{self._escape_html(entry.get("title", ""))}</h1>\n'
            f'    {entry["body"]}\n' "</section>"
            for i, entry in enumerate(chapter_entries)
        )

        title = self._escape_html(book_info.get("title", "Untitled"))
        return (
            "<!DOCTYPE html>\n<html>\n<head>\n"
            f'    <meta charset="utf-8">\n'
            f"    <title>{title}</title>\n"
            f"    <style>{print_css}</style>\n"
            f"    <style>{original_css}</style>\n"
            f"</head>\n<body>\n"
            f"    {cover_html}\n"
            f"    {toc_html}\n"
            f"    {chapters_html}\n"
            "</body>\n</html>"
        )

    def _generate_cover_html(self, book_info: dict, cover_image: str | None) -> str:
        title = self._escape_html(book_info.get("title", "Untitled"))
        authors = self._escape_html(
            ", ".join(str(a) for a in book_info.get("authors", []) if a)
        )
        publishers = self._escape_html(
            ", ".join(str(p) for p in book_info.get("publishers", []) if p)
        )
        cover_img = (
            f'<img src="Images/{self._escape_html_attr(cover_image)}" alt="Cover">'
            if cover_image
            else ""
        )
        author_html = f'<p class="authors">{authors}</p>' if authors else ""
        publisher_html = f'<p class="publisher">{publishers}</p>' if publishers else ""

        return (
            '<section class="cover-page">\n'
            f"    {cover_img}\n"
            f"    <h1>{title}</h1>\n"
            f"    {author_html}\n"
            f"    {publisher_html}\n"
            "</section>"
        )

    def _generate_toc_html(
        self,
        toc: list[dict],
        chapter_entries: list[dict],
        chapter_anchor_by_href: dict[str, str],
        fragment_anchor_by_key: dict[str, str],
    ) -> str:
        normalized = self._normalize_toc_items(
            toc or [],
            chapter_anchor_by_href,
            fragment_anchor_by_key,
        ) or self._build_toc_from_chapters(chapter_entries)

        if not normalized:
            return ""

        def render_item(item: dict) -> str:
            title = self._escape_html(item.get("title", "Untitled"))
            anchor = item.get("anchor_id")
            link = (
                f'<a href="#{self._escape_html_attr(anchor)}">{title}</a>'
                if anchor
                else f"<span>{title}</span>"
            )
            children_html = ""
            if item.get("children"):
                inner = "".join(f"<li>{render_item(c)}</li>" for c in item["children"])
                children_html = f"<ul>{inner}</ul>"
            return f"{link}{children_html}"

        items = "".join(f"<li>{render_item(item)}</li>" for item in normalized)
        return (
            '<section class="toc-page">\n'
            "    <h2>Table of Contents</h2>\n"
            f"    <ul>{items}</ul>\n"
            "</section>"
        )

    def _extract_chapter_body(self, xhtml_path: Path) -> str:
        """Extrae el contenido del body de un archivo XHTML.

        Usa BeautifulSoup/lxml si está disponible; fallback a regex si no.
        El fallback es menos preciso: puede incluir atributos de <body> como texto.
        """
        content = xhtml_path.read_text(encoding="utf-8")

        if _BS4_AVAILABLE:
            try:
                soup = _BeautifulSoup(content, "lxml")
                if soup.body:
                    return "".join(str(n) for n in soup.body.contents)
            except Exception:
                logger.warning(
                    "BeautifulSoup falló al parsear %s; usando regex.", xhtml_path.name
                )

        body_match = re.search(
            r"<body[^>]*>(.*?)</body>", content, re.DOTALL | re.IGNORECASE
        )
        if body_match:
            return body_match.group(1)

        logger.warning(
            "No se pudo extraer body de %s; el capítulo puede tener formato incorrecto.",
            xhtml_path.name,
        )
        return content

    def _extract_chapter_body_with_fragment_aliases(
        self,
        xhtml_path: Path,
        chapter_anchor: str,
        used_ids: set[str],
    ) -> tuple[str, dict[str, str]]:
        """Extrae body y construye mapa de fragmentos internos a IDs únicos del PDF."""
        if not _BS4_AVAILABLE:
            logger.warning(
                "bs4/lxml no disponibles; los links internos del capítulo %s no serán reescritos.",
                xhtml_path.name,
            )
            return self._extract_chapter_body(xhtml_path), {}

        content = xhtml_path.read_text(encoding="utf-8")
        try:
            soup = _BeautifulSoup(content, "lxml")
            body = soup.body or soup

            fragment_anchor_by_fragment: dict[str, str] = {}
            for node in body.find_all(True):
                fragment = self._normalize_fragment(node.get("id") or node.get("name"))
                if not fragment:
                    continue
                alias = self._unique_html_id(
                    self._make_html_id(
                        f"{chapter_anchor}-{fragment}", f"{chapter_anchor}-fragment"
                    ),
                    used_ids,
                    f"{chapter_anchor}-fragment",
                )
                node["id"] = alias
                fragment_anchor_by_fragment[fragment] = alias

            for anchor in body.find_all("a", href=True):
                href = str(anchor.get("href") or "").strip()
                if href.startswith("#"):
                    frag = self._normalize_fragment(href)
                    if alias := fragment_anchor_by_fragment.get(frag):
                        anchor["href"] = f"#{alias}"

            return "".join(str(n) for n in body.contents), fragment_anchor_by_fragment

        except Exception:
            logger.warning(
                "Error procesando fragmentos de %s; usando extracción simple.",
                xhtml_path.name,
                exc_info=True,
            )
            return self._extract_chapter_body(xhtml_path), {}

    def _rewrite_internal_book_links(self, entries: list[dict]) -> None:
        """Reescribe hrefs cross-capítulo para que apunten a anclas del PDF."""
        if not entries or not _BS4_AVAILABLE:
            if entries and not _BS4_AVAILABLE:
                logger.warning(
                    "bs4/lxml no disponibles; links entre capítulos no serán reescritos."
                )
            return

        chapter_anchor_by_href = {
            e["href"]: e["anchor_id"]
            for e in entries
            if e.get("href") and e.get("anchor_id")
        }
        fragment_anchor_by_key = {
            f"{e['href']}#{frag}": anchor
            for e in entries
            for frag, anchor in (e.get("fragment_anchor_by_fragment") or {}).items()
            if e.get("href") and frag and anchor
        }

        for entry in entries:
            body_html = entry.get("body") or ""
            current_href = entry.get("href") or ""
            if not body_html or not current_href:
                continue

            try:
                soup = _BeautifulSoup(body_html, "lxml")
            except Exception:
                logger.warning(
                    "Error parseando body de %r para reescritura de links.",
                    current_href,
                )
                continue

            changed = False
            for anchor in soup.find_all("a", href=True):
                resolved = self._resolve_internal_target_href(
                    current_href, str(anchor.get("href") or "").strip()
                )
                if not resolved:
                    continue
                target_href, fragment = resolved
                target_anchor = (
                    fragment and fragment_anchor_by_key.get(f"{target_href}#{fragment}")
                ) or chapter_anchor_by_href.get(target_href)
                if target_anchor:
                    anchor["href"] = f"#{target_anchor}"
                    changed = True

            if changed:
                container = soup.body or soup
                entry["body"] = "".join(str(n) for n in container.contents)

    def _load_css_files(self, oebps: Path, css_files: list[str]) -> str:
        """Carga y concatena los archivos CSS de la carpeta Styles.

        Usa los nombres reales de ``css_files`` si se proporcionan;
        si no, carga todos los Style*.css disponibles.
        """
        styles_dir = oebps / "Styles"
        css_parts: list[str] = []

        if css_files:
            for name in css_files:
                css_path = styles_dir / Path(name).name
                if css_path.exists() and css_path.is_file():
                    css_parts.append(css_path.read_text(encoding="utf-8"))
                else:
                    logger.debug("CSS no encontrado: %s", css_path)
        elif styles_dir.exists():
            for css_path in sorted(styles_dir.glob("Style*.css")):
                if css_path.is_file():
                    css_parts.append(css_path.read_text(encoding="utf-8"))

        return "\n".join(css_parts)

    def _get_print_css(self) -> str:
        css_path = Path(__file__).parent / "pdf_styles" / "print.css"
        if css_path.exists():
            return css_path.read_text(encoding="utf-8")
        logger.debug(
            "print.css no encontrado en %s; usando CSS embebido.", css_path.parent
        )
        return self._get_fallback_print_css()

    def _get_fallback_print_css(self) -> str:
        return """
@page {
    size: Letter;
    margin: 1in 0.75in;
    @bottom-center { content: counter(page); font-size: 9pt; }
}
@page :first { @bottom-center { content: none; } }
.cover-page { page-break-after: always; text-align: center; padding-top: 2in; }
.cover-page img { max-width: 100%; max-height: 6in; }
.cover-page h1 { font-size: 24pt; margin-top: 1in; }
.cover-page .authors { font-size: 14pt; color: #333; margin-top: 0.5in; }
.toc-page { page-break-after: always; }
.toc-page h2 { font-size: 18pt; margin-bottom: 1em; }
.toc-page ul { list-style: none; padding: 0; }
.toc-page li { margin: 0.5em 0; }
.toc-page a { color: #000; text-decoration: none; }
.chapter { page-break-before: always; }
.chapter:first-of-type { page-break-before: auto; }
.chapter-title { font-size: 20pt; margin-bottom: 1em; bookmark-level: 1; bookmark-label: content(); }
img { max-width: 100%; height: auto; }
figure { page-break-inside: avoid; }
pre, code { font-family: "Courier New", monospace; font-size: 9pt; background: #f5f5f5; padding: 0.5em; page-break-inside: avoid; }
table { page-break-inside: avoid; border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #ddd; padding: 0.5em; }
p { orphans: 3; widows: 3; }
"""

    def _resolve_cover_image(self, oebps: Path, cover_image: str | None) -> str | None:
        if not cover_image:
            return None
        name = Path(str(cover_image)).name
        path = oebps / "Images" / name
        if path.exists() and path.is_file():
            return name
        logger.debug("Imagen de portada no encontrada: %s", path)
        return None

    def _collect_chapter_entries(self, oebps: Path, chapters: list[dict]) -> list[dict]:
        entries: list[dict] = []
        used_ids: set[str] = set()
        seen_hrefs: set[str] = set()

        for index, chapter in enumerate(
            sorted(chapters, key=lambda c: c.get("order", 0)), start=1
        ):
            href = self._normalize_chapter_href(chapter.get("filename"))
            if not href or href in seen_hrefs:
                continue

            xhtml_path = oebps.joinpath(*PurePosixPath(href).parts)
            if not xhtml_path.exists() or not xhtml_path.is_file():
                logger.debug("Capítulo no encontrado en disco: %s", xhtml_path)
                continue

            title = str(chapter.get("title") or Path(href).stem)
            anchor = self._unique_html_id(
                self._make_html_id(Path(href).stem, f"chapter-{index}"),
                used_ids,
                f"chapter-{index}",
            )
            body, fragment_map = self._extract_chapter_body_with_fragment_aliases(
                xhtml_path,
                anchor,
                used_ids,
            )

            entries.append(
                {
                    "title": title,
                    "body": body,
                    "href": href,
                    "anchor_id": anchor,
                    "fragment_anchor_by_fragment": fragment_map,
                }
            )
            seen_hrefs.add(href)

        self._rewrite_internal_book_links(entries)
        return entries

    def _build_toc_from_chapters(self, chapter_entries: list[dict]) -> list[dict]:
        return [
            {
                "title": e.get("title") or "Untitled",
                "anchor_id": e["anchor_id"],
                "children": [],
            }
            for e in chapter_entries
        ]

    def _normalize_toc_items(
        self,
        toc_items: list[dict],
        chapter_anchor_by_href: dict[str, str],
        fragment_anchor_by_key: dict[str, str],
    ) -> list[dict]:
        normalized = []
        for item in toc_items:
            if not isinstance(item, dict):
                continue
            children = self._normalize_toc_items(
                item.get("children") or [],
                chapter_anchor_by_href,
                fragment_anchor_by_key,
            )
            title = str(item.get("title") or "").strip()
            anchor = self._resolve_toc_anchor(
                item, chapter_anchor_by_href, fragment_anchor_by_key
            )

            if not title:
                if anchor:
                    title = anchor
                elif children:
                    title = "Section"
                else:
                    continue

            normalized.append(
                {"title": title, "anchor_id": anchor, "children": children}
            )

        return normalized

    def _resolve_toc_anchor(
        self,
        toc_item: dict,
        chapter_anchor_by_href: dict[str, str],
        fragment_anchor_by_key: dict[str, str],
    ) -> str | None:
        raw = str(toc_item.get("reference_id") or toc_item.get("href") or "").strip()
        fragment = self._normalize_fragment(toc_item.get("fragment"))

        if "#" in raw:
            raw, inline_frag = raw.split("#", 1)
            fragment = fragment or self._normalize_fragment(inline_frag)

        href = self._normalize_chapter_href(raw)
        if not href:
            return None

        if fragment:
            if anchor := fragment_anchor_by_key.get(f"{href}#{fragment}"):
                return anchor

        return chapter_anchor_by_href.get(href)

    def _normalize_chapter_href(self, reference: str | None) -> str:
        if not reference:
            return ""

        href = str(reference).strip()
        if "-/" in href:
            href = href.split("-/", 1)[1]

        href = href.split("?", 1)[0].split("#", 1)[0]
        href = href.replace("\\", "/").lstrip("/")
        if not href:
            return ""

        parts = [p for p in PurePosixPath(href).parts if p and p != "."]
        if not parts or ".." in parts:
            return ""

        normalized = str(PurePosixPath(*parts))
        lower = normalized.lower()
        if lower.endswith(".html"):
            normalized = f"{normalized[:-5]}.xhtml"
        elif lower.endswith(".htm"):
            normalized = f"{normalized[:-4]}.xhtml"
        elif not lower.endswith(".xhtml") and not Path(normalized).suffix:
            normalized = f"{normalized}.xhtml"

        return normalized

    def _normalize_fragment(self, fragment: str | None) -> str:
        if not fragment:
            return ""
        return unquote(str(fragment).strip().lstrip("#"))

    def _resolve_internal_target_href(
        self, current_href: str, raw_href: str
    ) -> tuple[str, str] | None:
        value = str(raw_href or "").strip()
        if not value:
            return None

        lower = value.lower()
        if lower.startswith(
            ("mailto:", "tel:", "javascript:", "data:", "http://", "https://", "//")
        ):
            return None

        value = value.split("?", 1)[0]
        path_part, _, fragment = value.partition("#")
        normalized_fragment = self._normalize_fragment(fragment)

        if not path_part:
            return current_href, normalized_fragment

        if path_part.startswith("/"):
            candidate = path_part.lstrip("/")
        else:
            current_dir = PurePosixPath(current_href).parent.as_posix()
            candidate = posixpath.normpath(posixpath.join(current_dir, path_part))
            if candidate.startswith("../") or candidate == "..":
                return None
            candidate = candidate.lstrip("/")

        normalized = self._normalize_chapter_href(candidate)
        return (normalized, normalized_fragment) if normalized else None

    def _make_html_id(self, value: str | None, fallback: str) -> str:
        """Genera un ID HTML válido a partir de value; NO garantiza unicidad."""
        normalized = re.sub(r"[^A-Za-z0-9_-]+", "-", str(value or "")).strip("-_")
        if not normalized:
            return fallback
        if normalized[0].isdigit():
            return f"{fallback}-{normalized}"
        return normalized

    def _unique_html_id(self, value: str, used_ids: set[str], fallback: str) -> str:
        """Garantiza unicidad añadiendo sufijo numérico si es necesario."""
        base = self._make_html_id(value, fallback)
        candidate = base
        suffix = 2
        while candidate in used_ids:
            candidate = f"{base}-{suffix}"
            suffix += 1
        used_ids.add(candidate)
        return candidate

    def _safe_filename_stem(self, *candidates: str | None, fallback: str) -> str:
        """Retorna el primer candidato que produzca un nombre de archivo válido."""
        for candidate in candidates:
            if candidate is None:
                continue
            safe = sanitize_filename(str(candidate)).strip().strip(".")
            if safe and safe not in {".", ".."}:
                return safe
        return fallback

    def _escape_html(self, text: str) -> str:
        return html.escape(str(text)) if text else ""

    def _escape_html_attr(self, text: str) -> str:
        return html.escape(str(text), quote=True) if text else ""
