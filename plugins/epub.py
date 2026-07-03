import html
import re
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from utils import sanitize_filename

from .base import Plugin


class EpubPlugin(Plugin):
    def generate(
        self,
        book_info: dict,
        chapters: list[dict],
        toc: list[dict],
        output_dir: Path,
        css_files: list[str],
        cover_image: str | None = None,
    ) -> Path:
        oebps = output_dir / "OEBPS"
        oebps.mkdir(parents=True, exist_ok=True)
        (output_dir / "META-INF").mkdir(exist_ok=True)

        self._write_mimetype(output_dir)
        self._write_container_xml(output_dir)
        self._write_content_opf(
            oebps=oebps,
            book_info=book_info,
            chapter_entries=chapters,
            css_files=css_files,
            cover_image=cover_image,
        )
        self._write_toc_ncx(oebps, book_info, toc)
        self._write_nav_xhtml(oebps, book_info, toc)

        # Resolve all internal links so every fragment points to the file
        # that actually contains it. This prevents RSC-012 errors in epubcheck.
        self._resolve_internal_links(oebps)
        self._validate_manifest_files(oebps, chapters)

        # Use sanitized title for epub filename
        epub_name = sanitize_filename(book_info.get("title", book_info["id"]))
        epub_path = output_dir / f"{epub_name}.epub"
        self._create_epub_zip(output_dir, epub_path)
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
                artifact.unlink()
            elif artifact.is_dir():
                shutil.rmtree(artifact)

    def _write_mimetype(self, output_dir: Path) -> None:
        (output_dir / "mimetype").write_text("application/epub+zip", encoding="utf-8")

    def _write_container_xml(self, output_dir: Path) -> None:
        content = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""
        (output_dir / "META-INF" / "container.xml").write_text(content, encoding="utf-8")

    @staticmethod
    def _sanitize_xml_text(text: str) -> str:
        """Replace smart quotes and normalize text for XML output."""
        if not isinstance(text, str):
            text = str(text)
        # Replace Windows-1252 smart quotes with ASCII equivalents
        return (
            text.replace("\x93", '"')
            .replace("\x94", '"')
            .replace("\x92", "'")
            .replace("\x96", "--")
            .replace("\x97", "--")
        )

    @staticmethod
    def _sanitize_xml_id(raw: str) -> str:
        import re

        sanitized = re.sub(r"[^A-Za-z0-9_.\-]", "_", raw)
        if sanitized and sanitized[0].isdigit():
            sanitized = "_" + sanitized
        return sanitized or "_id"

    def _write_content_opf(
        self,
        oebps: Path,
        book_info: dict,
        chapter_entries: list[dict] | None = None,
        chapters: list[dict] | None = None,
        css_files: list[str] | None = None,
        cover_image: str | None = None,
    ) -> None:
        """Write the EPUB package document.

        Accepts ``chapter_entries`` (new) or ``chapters`` (legacy alias).
        ``css_files`` is also a keyword-only argument.
        """
        if chapter_entries is None:
            chapter_entries = chapters or []
        if css_files is None:
            css_files = []
        title = html.escape(self._sanitize_xml_text(book_info.get("title", "Unknown")))
        authors = book_info.get("authors", [])
        isbn = book_info.get("isbn", book_info.get("id", "unknown"))
        description = html.escape(self._sanitize_xml_text(book_info.get("description", "")[:500]))
        publishers = book_info.get("publishers", [])
        language = book_info.get("language", "en")
        pub_date = book_info.get("publication_date", "")

        author_xml = ""
        for author in authors:
            author_xml += (
                f"    <dc:creator>{html.escape(self._sanitize_xml_text(author))}</dc:creator>\n"
            )

        publisher_xml = ""
        for pub in publishers:
            publisher_xml += (
                f"    <dc:publisher>{html.escape(self._sanitize_xml_text(pub))}</dc:publisher>\n"
            )

        manifest_items = [
            '    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
            '    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        ]

        for i, ch in enumerate(chapter_entries):
            filename = ch["filename"].replace(".html", ".xhtml")
            item_id = f"ch{i:03d}"
            manifest_items.append(
                f'    <item id="{item_id}" href="{filename}" media-type="application/xhtml+xml"/>'
            )

        for i, _css in enumerate(css_files):
            manifest_items.append(
                f'    <item id="css{i:02d}" href="Styles/Style{i:02d}.css" media-type="text/css"/>'
            )

        cover_image_id = None
        if cover_image:
            cover_image_id = f"img_{Path(cover_image).stem}"

        images_dir = oebps / "Images"
        used_img_ids: set[str] = set()
        if images_dir.exists():
            for img_file in images_dir.iterdir():
                img_id = f"img_{img_file.stem}"
                if cover_image_id and img_file.name == cover_image:
                    continue
                if img_id in used_img_ids:
                    img_id = f"{img_id}_{img_file.suffix.lstrip('.')}"
                used_img_ids.add(img_id)
                media_type = self._get_image_media_type(img_file.suffix)
                properties = ""
                if cover_image_id and img_id == cover_image_id:
                    properties = ' properties="cover-image"'
                manifest_items.append(
                    f'    <item id="{img_id}" href="Images/{html.escape(img_file.name, quote=True)}" media-type="{media_type}"{properties}/>'
                )

        spine_items = []
        for i, _ch in enumerate(chapter_entries):
            spine_items.append(f'    <itemref idref="ch{i:03d}"/>')

        modified_timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        content = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="bookid" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/">
    <dc:title>{title}</dc:title>
{author_xml}{publisher_xml}    <dc:description>{description}</dc:description>
    <dc:language>{language}</dc:language>
    <dc:identifier id="bookid">{html.escape(isbn, quote=True)}</dc:identifier>
    <dc:date>{html.escape(pub_date, quote=True)}</dc:date>
    <meta property="dcterms:modified">{modified_timestamp}</meta>
  </metadata>
  <manifest>
{chr(10).join(manifest_items)}
  </manifest>
  <spine toc="ncx">
{chr(10).join(spine_items)}
  </spine>
</package>"""

        (oebps / "content.opf").write_text(content, encoding="utf-8")

    def _write_toc_ncx(self, oebps: Path, book_info: dict, toc: list[dict]) -> None:
        title = html.escape(book_info.get("title", "Unknown"))
        isbn = book_info.get("isbn", book_info.get("id", "unknown"))
        authors = ", ".join(book_info.get("authors", ["Unknown"]))

        max_depth = self._get_max_depth(toc)
        nav_points, _ = self._build_nav_points(toc, 1)

        content = f'''<?xml version="1.0" encoding="utf-8" standalone="no"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta content="{html.escape(isbn, quote=True)}" name="dtb:uid"/>
    <meta content="{max_depth}" name="dtb:depth"/>
    <meta content="0" name="dtb:totalPageCount"/>
    <meta content="0" name="dtb:maxPageNumber"/>
  </head>
  <docTitle>
    <text>{title}</text>
  </docTitle>
  <docAuthor>
    <text>{html.escape(self._sanitize_xml_text(authors))}</text>
  </docAuthor>
  <navMap>
{nav_points}
  </navMap>
</ncx>'''

        (oebps / "toc.ncx").write_text(content, encoding="utf-8")

    def _write_nav_xhtml(self, oebps: Path, book_info: dict, toc: list[dict]) -> None:
        """Generate EPUB 3 navigation document (nav.xhtml)."""
        title = html.escape(self._sanitize_xml_text(book_info.get("title", "Unknown")))
        nav_items = self._build_nav_ol(toc)

        content = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
  <title>{title}</title>
</head>
<body>
  <nav epub:type="toc" id="toc">
    <h1>Table of Contents</h1>
    <ol>
{nav_items}
    </ol>
  </nav>
</body>
</html>"""

        (oebps / "nav.xhtml").write_text(content, encoding="utf-8")

    def _build_nav_points(
        self, toc_items: list[dict], play_order: int, indent: int = 4
    ) -> tuple[str, int]:
        result = []
        spaces = " " * indent

        for item in toc_items:
            nav_id = self._sanitize_xml_id(
                item.get("fragment") or item.get("ourn", "").split(":")[-1].replace(".html", "")
            )
            label = html.escape(self._sanitize_xml_text(item.get("title", "")))
            href = item.get("reference_id", "").split("-/")[-1] if item.get("reference_id") else ""
            parts = urlsplit(href)
            href = urlunsplit(parts._replace(path=parts.path.replace(".html", ".xhtml")))

            if item.get("fragment"):
                href = f"{href}#{item['fragment']}"

            result.append(
                f'{spaces}<navPoint id="{html.escape(nav_id, quote=True)}" playOrder="{play_order}">'
            )
            result.append(f"{spaces}  <navLabel><text>{label}</text></navLabel>")
            result.append(f'{spaces}  <content src="{html.escape(href, quote=True)}"/>')

            play_order += 1

            children = item.get("children", [])
            if children:
                child_points, play_order = self._build_nav_points(children, play_order, indent + 2)
                result.append(child_points)

            result.append(f"{spaces}</navPoint>")

        return "\n".join(result), play_order

    def _build_nav_ol(self, toc_items: list[dict], indent: int = 6) -> str:
        """Build ordered list items for nav.xhtml navigation (EPUB 3)."""
        result = []
        spaces = " " * indent

        for item in toc_items:
            label = html.escape(self._sanitize_xml_text(item.get("title", "")))
            href = item.get("reference_id", "").split("-/")[-1] if item.get("reference_id") else ""
            parts = urlsplit(href)
            href = urlunsplit(parts._replace(path=parts.path.replace(".html", ".xhtml")))

            if item.get("fragment"):
                href = f"{href}#{item['fragment']}"

            children = item.get("children", [])
            if children:
                child_ol = self._build_nav_ol(children, indent + 2)
                result.append(f"{spaces}<li>")
                result.append(f'{spaces}  <a href="{html.escape(href, quote=True)}">{label}</a>')
                result.append(f"{spaces}  <ol>")
                result.append(child_ol)
                result.append(f"{spaces}  </ol>")
                result.append(f"{spaces}</li>")
            else:
                result.append(
                    f'{spaces}<li><a href="{html.escape(href, quote=True)}">{label}</a></li>'
                )

        return "\n".join(result)

    def _get_max_depth(self, toc_items: list[dict], current: int = 1) -> int:
        max_d = current
        for item in toc_items:
            children = item.get("children", [])
            if children:
                max_d = max(max_d, self._get_max_depth(children, current + 1))
        return max_d

    def _get_image_media_type(self, suffix: str) -> str:
        types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
        }
        return types.get(suffix.lower(), "application/octet-stream")

    def _validate_manifest_files(self, oebps: Path, chapters: list[dict]) -> None:
        missing = []
        for chapter in chapters:
            filename = chapter["filename"].replace(".html", ".xhtml")
            if not (oebps / filename).is_file():
                missing.append(filename)

        if missing:
            preview = ", ".join(missing[:6])
            remaining = len(missing) - 6
            suffix = f" and {remaining} more" if remaining > 0 else ""
            raise RuntimeError(f"EPUB build is missing chapter files: {preview}{suffix}")

    def _resolve_internal_links(self, oebps: Path) -> None:
        """Rewrite all internal hrefs so every fragment points to the file that
        actually contains it.  Drops fragments that don't exist anywhere, which
        prevents RSC-012 errors in epubcheck."""

        # 1. Build a global id → filename map across every XHTML file.
        id_map: dict[str, str] = {}
        for xhtml in oebps.rglob("*.xhtml"):
            text = xhtml.read_text(encoding="utf-8")
            for m in re.finditer(r'\bid="([^"]+)"', text):
                id_map[m.group(1)] = xhtml.name
            for m in re.finditer(r'\bname="([^"]+)"', text):
                if m.group(1) not in id_map:
                    id_map[m.group(1)] = xhtml.name

        if not id_map:
            return

        # 2. Rewrite hrefs and srcs in every XHTML (including nav.xhtml).
        for xhtml in oebps.rglob("*.xhtml"):
            text = xhtml.read_text(encoding="utf-8")
            original = text

            def _rewrite(match: re.Match) -> str:
                val = match.group(1)
                if "#" not in val:
                    return match.group(0)
                file_part, frag = val.split("#", 1)
                target = id_map.get(frag)
                if target is None:
                    # Fragment doesn't exist anywhere — drop it.
                    if file_part:
                        return f'{match.group(0).split("=")[0]}="{file_part}"'
                    return f'{match.group(0).split("=")[0]}=""'
                if not file_part:
                    # Bare fragment like href="#id" → href="file.xhtml#id"
                    return f'{match.group(0).split("=")[0]}="{target}#{frag}"'
                # Fragment exists; if it moved to a different file, correct it.
                if file_part != target:
                    return f'{match.group(0).split("=")[0]}="{target}#{frag}"'
                return match.group(0)

            text = re.sub(r'href="([^"]*)"', _rewrite, text)
            text = re.sub(r'src="([^"]*)"', _rewrite, text)

            if text != original:
                xhtml.write_text(text, encoding="utf-8")

        # 3. Also fix any malformed self-closing tags introduced by earlier steps.
        void_tags = (
            "br",
            "img",
            "input",
            "meta",
            "link",
            "hr",
            "source",
            "track",
            "wbr",
            "area",
            "base",
            "col",
            "embed",
            "param",
        )
        for xhtml in oebps.rglob("*.xhtml"):
            text = xhtml.read_text(encoding="utf-8")
            original = text
            for tag in void_tags:
                text = re.sub(
                    rf"<{tag}\b([^>]*?)\s*/\s*/>",
                    rf"<{tag}\1 />",
                    text,
                    flags=re.IGNORECASE,
                )
            if text != original:
                xhtml.write_text(text, encoding="utf-8")

    def _create_epub_zip(self, output_dir: Path, epub_path: Path) -> None:
        """Create the EPUB zip archive.

        Only the EPUB-specific subtrees (``META-INF/`` and ``OEBPS/``) are
        packaged, plus the required ``mimetype`` file at the archive root.
        Other files in ``output_dir`` (PDF, Markdown, JSON sidecars, etc.)
        are deliberately excluded so they don't pollute the EPUB.
        """
        with zipfile.ZipFile(epub_path, "w", zipfile.ZIP_DEFLATED) as zf:
            mimetype_path = output_dir / "mimetype"
            if mimetype_path.exists():
                zf.write(mimetype_path, "mimetype", compress_type=zipfile.ZIP_STORED)

            for root in (output_dir / "META-INF", output_dir / "OEBPS"):
                if not root.exists():
                    continue
                for file_path in root.rglob("*"):
                    if not file_path.is_file():
                        continue
                    # Skip non-EPUB artifacts (e.g. PDF covers placed under OEBPS/).
                    suffix = file_path.suffix.lower()
                    if suffix in {".pdf"}:
                        continue
                    arcname = file_path.relative_to(output_dir)
                    zf.write(file_path, arcname)
