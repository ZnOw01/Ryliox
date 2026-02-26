"""EPUB generator plugin."""

from __future__ import annotations

import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from lxml import etree

from utils import sanitize_filename

from .base import Plugin

_CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"
_OPF_NS = "http://www.idpf.org/2007/opf"
_DC_NS = "http://purl.org/dc/elements/1.1/"
_DCTERMS_NS = "http://purl.org/dc/terms/"
_NCX_NS = "http://www.daisy.org/z3986/2005/ncx/"
_XHTML_NS = "http://www.w3.org/1999/xhtml"
_EPUB_NS = "http://www.idpf.org/2007/ops"

_IMAGE_MEDIA_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}

_PLACEHOLDER_TITLE_RE = re.compile(
    r"^(ch|chapter|section|sec|part)[-_ ]*\d+$", re.IGNORECASE
)
_XML_ID_STRIP_RE = re.compile(r"[^A-Za-z0-9._-]+")


class EpubPlugin(Plugin):
    """Assemble a valid EPUB package from downloaded chapter assets."""

    def generate(
        self,
        book_info: dict,
        chapters: list[dict],
        toc: list[dict],
        output_dir: Path,
        css_files: list[str],
        cover_image: str | None = None,
        cleanup_build_artifacts: bool = False,
    ) -> Path:
        output_dir = Path(output_dir)
        oebps = output_dir / "OEBPS"
        oebps.mkdir(parents=True, exist_ok=True)
        (output_dir / "META-INF").mkdir(exist_ok=True)

        chapter_entries = self._collect_existing_chapters(oebps, chapters)
        chapter_hrefs = {entry["href"] for entry in chapter_entries}
        chapter_titles_by_href = {entry["href"]: entry.get("title") or "" for entry in chapter_entries}

        normalized_toc = self._normalize_toc_items(
            toc or [],
            chapter_hrefs,
            chapter_titles_by_href,
        )
        if not normalized_toc:
            normalized_toc = self._build_toc_from_chapters(chapter_entries)

        default_toc_href = self._default_toc_href(chapter_entries)

        self._write_mimetype(output_dir)
        self._write_container_xml(output_dir)
        self._write_content_opf(
            oebps=oebps,
            book_info=book_info,
            chapter_entries=chapter_entries,
            css_files=css_files,
            cover_image=cover_image,
        )
        self._write_toc_ncx(
            oebps=oebps,
            book_info=book_info,
            toc=normalized_toc,
            default_href=default_toc_href,
        )
        self._write_nav_xhtml(
            oebps=oebps,
            book_info=book_info,
            toc=normalized_toc,
            default_href=default_toc_href,
        )

        epub_name = self._safe_output_stem(book_info, fallback="book")
        epub_path = output_dir / f"{epub_name}.epub"
        self._create_epub_zip(output_dir, epub_path)

        if cleanup_build_artifacts:
            self._cleanup_build_artifacts(output_dir)

        return epub_path

    def _cleanup_build_artifacts(self, output_dir: Path) -> None:
        """Remove intermediate EPUB build files after ZIP creation."""
        artifacts = [
            output_dir / "mimetype",
            output_dir / "META-INF",
            output_dir / "OEBPS",
        ]
        for artifact in artifacts:
            if artifact.is_file():
                artifact.unlink(missing_ok=True)
            elif artifact.is_dir():
                shutil.rmtree(artifact, ignore_errors=True)

    def _write_mimetype(self, output_dir: Path) -> None:
        (output_dir / "mimetype").write_bytes(b"application/epub+zip")

    def _write_container_xml(self, output_dir: Path) -> None:
        container = etree.Element(f"{{{_CONTAINER_NS}}}container", nsmap={None: _CONTAINER_NS})
        container.set("version", "1.0")
        rootfiles = etree.SubElement(container, f"{{{_CONTAINER_NS}}}rootfiles")
        etree.SubElement(
            rootfiles,
            f"{{{_CONTAINER_NS}}}rootfile",
            attrib={
                "full-path": "OEBPS/content.opf",
                "media-type": "application/oebps-package+xml",
            },
        )
        self._write_xml_document(output_dir / "META-INF" / "container.xml", container)

    def _write_content_opf(
        self,
        oebps: Path,
        book_info: dict,
        chapter_entries: list[dict],
        css_files: list[str],
        cover_image: str | None,
    ) -> None:
        title = str(book_info.get("title") or "Unknown")
        authors = book_info.get("authors") or []
        isbn = str(book_info.get("isbn") or book_info.get("id") or "unknown")
        description_raw = book_info.get("description") or ""
        description = str(description_raw)[:500]
        publishers = book_info.get("publishers") or []
        language = str(book_info.get("language") or "en")
        pub_date = str(book_info.get("publication_date") or "")

        package = etree.Element(
            f"{{{_OPF_NS}}}package",
            nsmap={None: _OPF_NS, "dc": _DC_NS, "dcterms": _DCTERMS_NS},
            attrib={"unique-identifier": "bookid", "version": "3.0"},
        )
        metadata = etree.SubElement(package, f"{{{_OPF_NS}}}metadata")
        etree.SubElement(metadata, f"{{{_DC_NS}}}title").text = title

        for author in authors:
            if author:
                etree.SubElement(metadata, f"{{{_DC_NS}}}creator").text = str(author)
        for publisher in publishers:
            if publisher:
                etree.SubElement(metadata, f"{{{_DC_NS}}}publisher").text = str(publisher)

        etree.SubElement(metadata, f"{{{_DC_NS}}}description").text = description
        etree.SubElement(metadata, f"{{{_DC_NS}}}language").text = language
        etree.SubElement(metadata, f"{{{_DC_NS}}}identifier", id="bookid").text = isbn
        etree.SubElement(metadata, f"{{{_DC_NS}}}date").text = pub_date

        modified_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        etree.SubElement(metadata, f"{{{_OPF_NS}}}meta", property="dcterms:modified").text = modified_timestamp

        manifest = etree.SubElement(package, f"{{{_OPF_NS}}}manifest")
        etree.SubElement(
            manifest,
            f"{{{_OPF_NS}}}item",
            id="ncx",
            href="toc.ncx",
            **{"media-type": "application/x-dtbncx+xml"},
        )
        etree.SubElement(
            manifest,
            f"{{{_OPF_NS}}}item",
            id="nav",
            href="nav.xhtml",
            properties="nav",
            **{"media-type": "application/xhtml+xml"},
        )

        used_item_ids = {"ncx", "nav"}
        spine = etree.SubElement(package, f"{{{_OPF_NS}}}spine", toc="ncx")

        for i, chapter in enumerate(chapter_entries):
            item_id = self._unique_xml_id(f"ch{i:03d}", used_item_ids, "ch")
            etree.SubElement(
                manifest,
                f"{{{_OPF_NS}}}item",
                id=item_id,
                href=str(chapter["href"]),
                **{"media-type": "application/xhtml+xml"},
            )
            etree.SubElement(spine, f"{{{_OPF_NS}}}itemref", idref=item_id)

        styles_dir = oebps / "Styles"
        for i, _ in enumerate(css_files):
            css_path = styles_dir / f"Style{i:02d}.css"
            if not css_path.exists():
                continue
            css_id = self._unique_xml_id(f"css{i:02d}", used_item_ids, "css")
            etree.SubElement(
                manifest,
                f"{{{_OPF_NS}}}item",
                id=css_id,
                href=f"Styles/Style{i:02d}.css",
                **{"media-type": "text/css"},
            )

        images_dir = oebps / "Images"
        cover_image_name = self._resolve_cover_image_name(images_dir, cover_image)

        if images_dir.exists():
            for i, img_file in enumerate(sorted(images_dir.iterdir(), key=lambda p: p.name.lower())):
                if not img_file.is_file():
                    continue
                img_id = self._unique_xml_id(f"img_{img_file.stem}", used_item_ids, f"img{i:03d}")
                media_type = self._get_image_media_type(img_file.suffix)
                image_item_attrs = {
                    "id": img_id,
                    "href": f"Images/{img_file.name}",
                    "media-type": media_type,
                }
                if cover_image_name and img_file.name == cover_image_name:
                    image_item_attrs["properties"] = "cover-image"
                etree.SubElement(
                    manifest,
                    f"{{{_OPF_NS}}}item",
                    attrib=image_item_attrs,
                )

        if not chapter_entries:
            etree.SubElement(spine, f"{{{_OPF_NS}}}itemref", idref="nav")

        self._write_xml_document(oebps / "content.opf", package)

    def _write_toc_ncx(
        self,
        oebps: Path,
        book_info: dict,
        toc: list[dict],
        default_href: str,
    ) -> None:
        title = str(book_info.get("title") or "Unknown")
        isbn = str(book_info.get("isbn") or book_info.get("id") or "unknown")
        author_values = [str(author) for author in (book_info.get("authors") or []) if author]
        authors = ", ".join(author_values) if author_values else "Unknown"

        ncx = etree.Element(f"{{{_NCX_NS}}}ncx", nsmap={None: _NCX_NS}, version="2005-1")
        head = etree.SubElement(ncx, f"{{{_NCX_NS}}}head")
        max_depth = self._get_max_depth(toc) if toc else 1

        etree.SubElement(head, f"{{{_NCX_NS}}}meta", content=f"ID:ISBN:{isbn}", name="dtb:uid")
        etree.SubElement(head, f"{{{_NCX_NS}}}meta", content=str(max_depth), name="dtb:depth")
        etree.SubElement(head, f"{{{_NCX_NS}}}meta", content="0", name="dtb:totalPageCount")
        etree.SubElement(head, f"{{{_NCX_NS}}}meta", content="0", name="dtb:maxPageNumber")

        doc_title = etree.SubElement(ncx, f"{{{_NCX_NS}}}docTitle")
        etree.SubElement(doc_title, f"{{{_NCX_NS}}}text").text = title
        doc_author = etree.SubElement(ncx, f"{{{_NCX_NS}}}docAuthor")
        etree.SubElement(doc_author, f"{{{_NCX_NS}}}text").text = authors

        nav_map = etree.SubElement(ncx, f"{{{_NCX_NS}}}navMap")
        nav_points, _, _ = self._build_ncx_nav_points(toc, 1, default_href, used_ids=set())

        if nav_points:
            for nav_point in nav_points:
                nav_map.append(nav_point)
        else:
            fallback_nav_point = etree.SubElement(
                nav_map,
                f"{{{_NCX_NS}}}navPoint",
                id="navpoint-1",
                playOrder="1",
            )
            nav_label = etree.SubElement(fallback_nav_point, f"{{{_NCX_NS}}}navLabel")
            etree.SubElement(nav_label, f"{{{_NCX_NS}}}text").text = "Start"
            etree.SubElement(fallback_nav_point, f"{{{_NCX_NS}}}content", src=str(default_href))

        self._write_xml_document(
            oebps / "toc.ncx",
            ncx,
            doctype=(
                '<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" '
                '"http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">'
            ),
        )

    def _write_nav_xhtml(
        self,
        oebps: Path,
        book_info: dict,
        toc: list[dict],
        default_href: str,
    ) -> None:
        """Generate EPUB 3 navigation document (nav.xhtml)."""
        title = str(book_info.get("title") or "Unknown")
        html_root = etree.Element(
            f"{{{_XHTML_NS}}}html",
            nsmap={None: _XHTML_NS, "epub": _EPUB_NS},
        )
        head = etree.SubElement(html_root, f"{{{_XHTML_NS}}}head")
        etree.SubElement(head, f"{{{_XHTML_NS}}}title").text = title
        body = etree.SubElement(html_root, f"{{{_XHTML_NS}}}body")
        nav = etree.SubElement(body, f"{{{_XHTML_NS}}}nav", id="toc")
        nav.set(f"{{{_EPUB_NS}}}type", "toc")
        etree.SubElement(nav, f"{{{_XHTML_NS}}}h1").text = "Table of Contents"

        nav_ol = etree.SubElement(nav, f"{{{_XHTML_NS}}}ol")

        if not self._append_nav_ol_items(nav_ol, toc):
            li = etree.SubElement(nav_ol, f"{{{_XHTML_NS}}}li")
            etree.SubElement(li, f"{{{_XHTML_NS}}}a", href=str(default_href)).text = "Start"

        self._write_xml_document(
            oebps / "nav.xhtml",
            html_root,
            doctype="<!DOCTYPE html>",
        )

    def _build_ncx_nav_points(
        self,
        toc_items: list[dict],
        play_order: int,
        default_href: str,
        used_ids: set[str],
    ) -> tuple[list, int, str | None]:
        nav_points = []
        first_href = None

        for item in toc_items:
            current_play_order = play_order
            play_order += 1

            children = item.get("children") or []
            child_points = []
            child_first_href = None

            if children:
                child_points, play_order, child_first_href = self._build_ncx_nav_points(
                    children,
                    play_order,
                    default_href,
                    used_ids,
                )

            href = item.get("href") or child_first_href or default_href
            if not href:
                continue

            if first_href is None:
                first_href = href

            nav_id = self._unique_xml_id(
                item.get("id") or item.get("href") or item.get("title") or f"navpoint-{current_play_order}",
                used_ids,
                f"navpoint-{current_play_order}",
            )
            nav_point = etree.Element(
                f"{{{_NCX_NS}}}navPoint",
                id=nav_id,
                playOrder=str(current_play_order),
            )
            nav_label = etree.SubElement(nav_point, f"{{{_NCX_NS}}}navLabel")
            etree.SubElement(nav_label, f"{{{_NCX_NS}}}text").text = str(item.get("title") or "")
            etree.SubElement(nav_point, f"{{{_NCX_NS}}}content", src=str(href))

            for child in child_points:
                nav_point.append(child)

            nav_points.append(nav_point)

        return nav_points, play_order, first_href

    def _append_nav_ol_items(self, ol_element: etree._Element, toc_items: list[dict]) -> bool:
        for item in toc_items:
            label = str(item.get("title") or "")
            href = item.get("href")
            children = item.get("children") or []

            li = etree.SubElement(ol_element, f"{{{_XHTML_NS}}}li")
            if href:
                etree.SubElement(li, f"{{{_XHTML_NS}}}a", href=str(href)).text = label
            else:
                etree.SubElement(li, f"{{{_XHTML_NS}}}span").text = label

            if children:
                child_ol = etree.SubElement(li, f"{{{_XHTML_NS}}}ol")
                self._append_nav_ol_items(child_ol, children)

        return bool(toc_items)

    def _write_xml_document(
        self,
        output_path: Path,
        root_element: etree._Element,
        doctype: str | None = None,
    ) -> None:
        output_path.write_bytes(
            etree.tostring(
                root_element,
                encoding="utf-8",
                xml_declaration=True,
                pretty_print=True,
                doctype=doctype,
            )
        )

    def _get_max_depth(self, toc_items: list[dict], current: int = 1) -> int:
        return max(
            (
                self._get_max_depth(item.get("children") or [], current + 1)
                for item in toc_items
                if item.get("children")
            ),
            default=current,
        )

    def _get_image_media_type(self, suffix: str) -> str:
        return _IMAGE_MEDIA_TYPES.get(suffix.lower(), "application/octet-stream")

    def _create_epub_zip(self, output_dir: Path, epub_path: Path) -> None:
        """Comprime el EPUB. El estándar exige que 'mimetype' sea el primer archivo, sin compresión."""
        with zipfile.ZipFile(epub_path, "w", zipfile.ZIP_DEFLATED) as zf:
            mimetype_path = output_dir / "mimetype"
            zf.write(mimetype_path, "mimetype", compress_type=zipfile.ZIP_STORED)

            for file_path in sorted(output_dir.rglob("*")):
                if not file_path.is_file() or file_path.name == "mimetype":
                    continue

                arcname = file_path.relative_to(output_dir).as_posix()
                if arcname.endswith(".epub"):
                    continue

                info = zipfile.ZipInfo(arcname)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (file_path.stat().st_mode & 0o777) << 16
                info.flag_bits |= (
                    0x800  # Forzar codificación UTF-8 para los nombres de archivo
                )

                with file_path.open("rb") as fh, zf.open(info, "w") as zfh:
                    shutil.copyfileobj(fh, zfh, length=1024 * 64)

    def _collect_existing_chapters(self, oebps: Path, chapters: list[dict]) -> list[dict]:
        chapter_entries = []
        seen_hrefs = set()

        for index, chapter in enumerate(chapters):
            href = self._normalize_chapter_href(chapter.get("filename"))
            if not href or href in seen_hrefs:
                continue

            chapter_path = oebps.joinpath(*PurePosixPath(href).parts)
            if not chapter_path.exists() or not chapter_path.is_file():
                continue

            title = self._resolve_chapter_title(chapter, chapter_path, href)
            chapter_entries.append(
                {
                    "title": title,
                    "href": href,
                    "order": chapter.get(
                        "order", index
                    ),  # Fallback index to preserve original layout
                }
            )
            seen_hrefs.add(href)

        return sorted(chapter_entries, key=self._chapter_sort_key)

    def _build_toc_from_chapters(self, chapter_entries: list[dict]) -> list[dict]:
        return [
            {
                "title": chapter.get("title") or Path(chapter["href"]).stem,
                "href": chapter["href"],
                "children": [],
            }
            for chapter in chapter_entries
        ]

    def _normalize_toc_items(
        self,
        toc_items: list[dict],
        chapter_hrefs: set[str],
        chapter_titles_by_href: dict[str, str],
    ) -> list[dict]:
        normalized = []

        for item in toc_items:
            if not isinstance(item, dict):
                continue

            children = self._normalize_toc_items(
                item.get("children") or [],
                chapter_hrefs,
                chapter_titles_by_href,
            )

            title = str(item.get("title") or "").strip()
            href = self._resolve_toc_href(item, chapter_hrefs)
            href_key = href.split("#", 1)[0] if href else ""
            chapter_title = chapter_titles_by_href.get(href_key, "") if href_key else ""

            if chapter_title and (not title or self._is_placeholder_title(title, href or chapter_title)):
                title = chapter_title

            if not title:
                if href:
                    title = Path(href.split("#", 1)[0]).stem
                elif children:
                    title = "Section"
                else:
                    continue

            normalized.append({
                "title": title,
                "href": href,
                "children": children,
            })

        return normalized

    def _resolve_toc_href(self, toc_item: dict, chapter_hrefs: set[str]) -> str | None:
        raw_reference = toc_item.get("reference_id") or toc_item.get("href") or ""
        reference = str(raw_reference).strip()
        fragment = self._normalize_fragment(toc_item.get("fragment"))

        if "#" in reference:
            reference, inline_fragment = reference.split("#", 1)
            if not fragment:
                fragment = self._normalize_fragment(inline_fragment)

        href = self._normalize_chapter_href(reference)
        if not href or href not in chapter_hrefs:
            return None

        if fragment:
            return f"{href}#{fragment}"
        return href

    def _default_toc_href(self, chapter_entries: list[dict]) -> str:
        if chapter_entries:
            return chapter_entries[0]["href"]
        return "nav.xhtml"

    def _normalize_chapter_href(self, reference: str | None) -> str:
        if reference is None:
            return ""

        href = str(reference).strip()
        if not href:
            return ""

        if "-/" in href:
            href = href.split("-/", 1)[1]

        href = href.split("?", 1)[0].split("#", 1)[0]
        href = href.replace("\\", "/").lstrip("/")

        if not href:
            return ""

        parts = [part for part in PurePosixPath(href).parts if part and part != "."]
        if not parts or ".." in parts:
            return ""

        normalized = str(PurePosixPath(*parts))
        lower_href = normalized.lower()

        if lower_href.endswith((".html", ".htm")):
            normalized = f"{normalized.rsplit('.', 1)[0]}.xhtml"
        elif not lower_href.endswith(".xhtml") and not Path(normalized).suffix:
            normalized = f"{normalized}.xhtml"

        return normalized

    def _normalize_fragment(self, fragment: str | None) -> str:
        if fragment is None:
            return ""
        return str(fragment).strip().lstrip("#")

    def _to_xml_id(self, value: str | None, fallback: str) -> str:
        normalized = _XML_ID_STRIP_RE.sub("-", str(value or "")).strip("-._")
        if not normalized:
            normalized = fallback
        if not re.match(r"^[A-Za-z_]", normalized):
            normalized = f"{fallback}-{normalized}"
        return normalized

    def _unique_xml_id(self, value: str | None, used_ids: set[str], fallback: str) -> str:
        base_id = self._to_xml_id(value, fallback)
        candidate = base_id
        suffix = 2

        while candidate in used_ids:
            candidate = f"{base_id}-{suffix}"
            suffix += 1

        used_ids.add(candidate)
        return candidate

    def _safe_output_stem(self, book_info: dict, fallback: str) -> str:
        candidates = (
            book_info.get("title"),
            book_info.get("id"),
            book_info.get("isbn"),
            fallback,
        )
        for candidate in candidates:
            if candidate is None:
                continue
            safe_name = sanitize_filename(str(candidate)).strip().strip(".")
            if safe_name and safe_name not in {".", ".."}:
                return safe_name

        return fallback

    def _resolve_cover_image_name(self, images_dir: Path, cover_image: str | None) -> str | None:
        if not images_dir.exists():
            return None

        if cover_image:
            explicit_name = Path(str(cover_image)).name
            explicit_path = images_dir / explicit_name
            if explicit_path.exists() and explicit_path.is_file():
                return explicit_name

        preferred = ("cover.jpg", "cover.jpeg", "cover.png", "cover.webp", "cover.gif")
        for name in preferred:
            candidate = images_dir / name
            if candidate.exists() and candidate.is_file():
                return name

        image_files = sorted([p for p in images_dir.iterdir() if p.is_file()], key=lambda p: p.name.lower())
        for image_file in image_files:
            if "cover" in image_file.stem.lower():
                return image_file.name

        if image_files:
            return image_files[0].name

        return None

    def _chapter_sort_key(self, chapter: dict) -> tuple[int, float]:
        href_name = Path(str(chapter.get("href", ""))).name.lower()
        try:
            order = float(chapter.get("order", float("inf")))
        except (TypeError, ValueError):
            order = float("inf")

        if "cover" in href_name:
            return (0, order)
        if "titlepage" in href_name or "title-page" in href_name:
            return (1, order)

        return (2, order)

    def _resolve_chapter_title(self, chapter: dict, chapter_path: Path, href: str) -> str:
        provided = str(chapter.get("title") or "").strip()
        extracted = self._extract_xhtml_title(chapter_path)

        if extracted and (not provided or self._is_placeholder_title(provided, href)):
            return extracted
        if provided:
            return provided
        if extracted:
            return extracted

        return Path(href).stem

    def _extract_xhtml_title(self, chapter_path: Path) -> str:
        try:
            parser = etree.XMLParser(recover=True)
            root = etree.parse(str(chapter_path), parser=parser).getroot()
            if root is None:
                return ""
        except Exception:
            return ""

        candidates = [
            root.xpath(
                "string(//*[local-name()='head']/*[local-name()='title'])"
            ).strip(),
            root.xpath(
                "string(//*[local-name()='body']//*[local-name()='h1'][1])"
            ).strip(),
            root.xpath(
                "string(//*[local-name()='body']//*[local-name()='h2'][1])"
            ).strip(),
        ]

        for candidate in candidates:
            if candidate:
                return " ".join(candidate.split())  # Normaliza espacios

        return ""

    def _is_placeholder_title(self, title: str, href: str) -> bool:
        normalized = " ".join(str(title or "").split()).strip().lower()
        if not normalized:
            return True

        stem = Path(str(href)).stem.lower()
        if normalized in {stem, stem.replace("-", " "), stem.replace("_", " ")}:
            return True

        return bool(_PLACEHOLDER_TITLE_RE.match(normalized))
