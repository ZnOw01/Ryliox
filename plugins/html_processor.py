"""HTML Processor Plugin."""

from __future__ import annotations

import hashlib
import html as html_lib
import re
from functools import cached_property
from pathlib import PurePosixPath
from urllib.parse import unquote, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag

try:
    import bleach
    from bleach.css_sanitizer import CSSSanitizer
except ImportError:
    bleach = None
    CSSSanitizer = None

import config

from .base import Plugin

_COVER_WORD_RE = re.compile(r"\bcover\b", re.IGNORECASE)


class HtmlProcessorPlugin(Plugin):
    _CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
    _HTML_EXTENSION_RE = re.compile(r"\.html$", re.IGNORECASE)
    _SRCSET_DESCRIPTOR_RE = re.compile(r"^\d+(\.\d+)?[wxh]$")

    _ALLOWED_HTML_TAGS = frozenset(
        {
            "a",
            "abbr",
            "article",
            "aside",
            "b",
            "blockquote",
            "br",
            "caption",
            "code",
            "col",
            "colgroup",
            "dd",
            "del",
            "details",
            "dfn",
            "div",
            "dl",
            "dt",
            "em",
            "figcaption",
            "figure",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "hr",
            "i",
            "img",
            "kbd",
            "li",
            "mark",
            "ol",
            "p",
            "pre",
            "q",
            "s",
            "samp",
            "section",
            "small",
            "source",
            "span",
            "strong",
            "sub",
            "summary",
            "sup",
            "table",
            "tbody",
            "td",
            "tfoot",
            "th",
            "thead",
            "tr",
            "u",
            "ul",
            "var",
            "picture",
            "style",
            "svg",
            "g",
            "path",
            "line",
            "polyline",
            "polygon",
            "circle",
            "ellipse",
            "rect",
            "text",
            "tspan",
            "defs",
            "use",
            "symbol",
            "title",
            "desc",
            "image",
        }
    )

    _GLOBAL_ALLOWED_ATTRIBUTES = frozenset(
        {
            "class",
            "dir",
            "epub:type",
            "id",
            "lang",
            "role",
            "style",
            "title",
            "xmlns",
            "viewbox",
        }
    )

    _TAG_ALLOWED_ATTRIBUTES = {
        "a": frozenset({"href", "name", "rel", "target", "title"}),
        "blockquote": frozenset({"cite"}),
        "col": frozenset({"span", "width"}),
        "colgroup": frozenset({"span", "width"}),
        "img": frozenset(
            {
                "alt",
                "decoding",
                "fetchpriority",
                "height",
                "loading",
                "src",
                "srcset",
                "sizes",
                "width",
                "data-src",
                "data-srcset",
            }
        ),
        "source": frozenset(
            {
                "media",
                "sizes",
                "src",
                "srcset",
                "type",
                "width",
                "height",
                "data-src",
                "data-srcset",
            }
        ),
        "ol": frozenset({"start", "reversed", "type"}),
        "td": frozenset({"colspan", "headers", "rowspan", "scope"}),
        "th": frozenset({"abbr", "colspan", "headers", "rowspan", "scope"}),
        "time": frozenset({"datetime"}),
        "svg": frozenset(
            {
                "xmlns",
                "viewbox",
                "width",
                "height",
                "preserveaspectratio",
                "aria-label",
                "focusable",
                "role",
                "fill",
                "stroke",
                "stroke-width",
                "transform",
            }
        ),
        "g": frozenset({"fill", "stroke", "stroke-width", "transform", "opacity"}),
        "path": frozenset(
            {"d", "fill", "stroke", "stroke-width", "transform", "opacity"}
        ),
        "line": frozenset(
            {"x1", "y1", "x2", "y2", "stroke", "stroke-width", "transform"}
        ),
        "polyline": frozenset(
            {"points", "fill", "stroke", "stroke-width", "transform"}
        ),
        "polygon": frozenset({"points", "fill", "stroke", "stroke-width", "transform"}),
        "circle": frozenset(
            {"cx", "cy", "r", "fill", "stroke", "stroke-width", "transform"}
        ),
        "ellipse": frozenset(
            {"cx", "cy", "rx", "ry", "fill", "stroke", "stroke-width", "transform"}
        ),
        "rect": frozenset(
            {
                "x",
                "y",
                "width",
                "height",
                "rx",
                "ry",
                "fill",
                "stroke",
                "stroke-width",
                "transform",
            }
        ),
        "text": frozenset(
            {
                "x",
                "y",
                "dx",
                "dy",
                "fill",
                "stroke",
                "font-size",
                "text-anchor",
                "transform",
            }
        ),
        "tspan": frozenset({"x", "y", "dx", "dy"}),
        "use": frozenset({"href", "x", "y", "width", "height"}),
        "image": frozenset(
            {
                "href",
                "xlink:href",
                "x",
                "y",
                "width",
                "height",
                "transform",
                "preserveaspectratio",
                "clip-path",
                "opacity",
            }
        ),
    }

    _ALLOWED_PROTOCOLS = frozenset({"http", "https", "mailto", "tel", "data"})
    _ALLOWED_CSS_PROPERTIES = frozenset(
        {
            "background",
            "background-color",
            "border",
            "border-bottom",
            "border-bottom-color",
            "border-bottom-style",
            "border-bottom-width",
            "border-collapse",
            "border-color",
            "border-left",
            "border-left-color",
            "border-left-style",
            "border-left-width",
            "border-right",
            "border-right-color",
            "border-right-style",
            "border-right-width",
            "border-spacing",
            "border-style",
            "border-top",
            "border-top-color",
            "border-top-style",
            "border-top-width",
            "border-width",
            "clear",
            "color",
            "display",
            "float",
            "font",
            "font-family",
            "font-size",
            "font-style",
            "font-variant",
            "font-weight",
            "height",
            "letter-spacing",
            "line-height",
            "list-style",
            "list-style-position",
            "list-style-type",
            "margin",
            "margin-bottom",
            "margin-left",
            "margin-right",
            "margin-top",
            "max-height",
            "max-width",
            "min-height",
            "min-width",
            "opacity",
            "overflow",
            "padding",
            "padding-bottom",
            "padding-left",
            "padding-right",
            "padding-top",
            "page-break-after",
            "page-break-before",
            "page-break-inside",
            "text-align",
            "text-decoration",
            "text-indent",
            "text-transform",
            "vertical-align",
            "white-space",
            "width",
            "word-break",
            "word-spacing",
            "word-wrap",
        }
    )

    @cached_property
    def _cleaner(self) -> "bleach.Cleaner":
        if bleach is None or CSSSanitizer is None:
            raise RuntimeError(
                "bleach is required to sanitize processed HTML. Install it with: pip install bleach"
            )
        return bleach.Cleaner(
            tags=self._ALLOWED_HTML_TAGS,
            attributes=self._is_allowed_attribute,
            protocols=self._ALLOWED_PROTOCOLS,
            strip=True,
            strip_comments=True,
            css_sanitizer=CSSSanitizer(
                allowed_css_properties=self._ALLOWED_CSS_PROPERTIES
            ),
        )

    def process(
        self,
        html: str,
        book_id: str,
        skip_images: bool = False,
        base_url: str = "",
        images_prefix: str = "Images",
    ) -> tuple[str, list[str]]:
        soup = BeautifulSoup(html, "lxml")
        images_found: list[str] = []

        content_div = soup.find("div", id="sbo-rt-content")
        if not content_div:
            content_div = soup.body or soup

        self._convert_svg_images(content_div)

        if skip_images:
            self._remove_images(content_div)
        else:
            images_found = self._rewrite_image_links(
                content_div, base_url, images_prefix
            )

        self._rewrite_href_links(content_div, book_id)
        self._handle_data_template_styles(content_div)

        sanitized_html = self._sanitize_processed_html(str(content_div))
        return sanitized_html, images_found

    def _remove_images(self, soup: Tag) -> None:
        for tag_name in ("picture", "img", "source"):
            for tag in soup.find_all(tag_name):
                tag.decompose()

    def _convert_svg_images(self, soup: Tag) -> None:
        for image_tag in soup.find_all("image"):
            href = image_tag.get("href") or image_tag.get("xlink:href")
            if not href:
                continue

            parent = image_tag.parent
            if parent and parent.name == "svg":
                continue

            img_tag = soup.new_tag("img", src=href)
            image_tag.replace_with(img_tag)

    def _rewrite_image_links(
        self,
        soup: Tag,
        base_url: str = "",
        images_prefix: str = "Images",
    ) -> list[str]:
        images: list[str] = []
        seen_sources: set[str] = set()

        def _add_image(original_url: str):
            if original_url and original_url not in seen_sources:
                seen_sources.add(original_url)
                images.append(original_url)

        image_tags = soup.find_all(
            lambda tag: tag.name == "img"
            or (
                tag.name == "source"
                and (
                    (tag.parent and tag.parent.name == "picture")
                    or str(tag.get("type", "")).lower().startswith("image/")
                )
            )
        )

        for tag in image_tags:
            for attr in ("src", "data-src"):
                value = tag.get(attr)
                if value:
                    rewritten, original = self._rewrite_image_value(
                        value, base_url, images_prefix
                    )
                    if rewritten:
                        tag[attr] = rewritten
                    if original:
                        _add_image(original)

            for attr in ("srcset", "data-srcset"):
                srcset = tag.get(attr)
                if srcset:
                    rewritten_srcset, originals = self._rewrite_srcset_value(
                        srcset, base_url, images_prefix
                    )
                    if rewritten_srcset:
                        tag[attr] = rewritten_srcset
                    for original in originals:
                        _add_image(original)

            if tag.name == "img" and not tag.get("src"):
                fallback_src = tag.get("data-src")
                if fallback_src:
                    tag["src"] = fallback_src
                else:
                    fallback_srcset = tag.get("srcset") or tag.get("data-srcset")
                    if fallback_srcset:
                        first_srcset = self._first_srcset_candidate(fallback_srcset)
                        if first_srcset:
                            tag["src"] = first_srcset

        return images

    def _rewrite_href_links(self, soup: Tag, book_id: str) -> None:
        for a in soup.find_all("a", href=True):
            a["href"] = self._rewrite_href(a["href"], book_id)

    def _handle_data_template_styles(self, soup: Tag) -> None:
        for style in soup.find_all("style", attrs={"data-template": True}):
            style.string = style["data-template"]
            del style["data-template"]

    def wrap_xhtml(self, content: str, css_files: list[str], title: str = "") -> str:
        safe_title = self._sanitize_title(title)
        css_links = "\n".join(
            f'<link href="{html_lib.escape(str(css), quote=True)}" rel="stylesheet" type="text/css"/>'
            for css in css_files
        )

        return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en">
<head>
<title>{safe_title}</title>
{css_links}
<style type="text/css">
body{{margin:1em;background-color:transparent!important;}}
</style>
</head>
<body>
{content}
</body>
</html>"""

    def image_filename_from_url(self, url: str) -> str | None:
        if not url:
            return None

        value = url.strip()
        if not value or value.startswith("data:"):
            return None

        parsed = urlparse(value)
        raw_filename = unquote(PurePosixPath(parsed.path).name)

        if not raw_filename:
            raw_filename = "asset"

        raw_path = PurePosixPath(raw_filename)
        raw_stem = raw_path.stem or "asset"
        raw_suffix = raw_path.suffix

        safe_stem = re.sub(r"[^A-Za-z0-9_-]", "_", raw_stem).strip("_")
        if not safe_stem:
            safe_stem = "asset"
        safe_suffix = re.sub(r"[^A-Za-z0-9.]", "", raw_suffix)[:12]

        digest = hashlib.sha1(
            value.encode("utf-8", errors="ignore"),
            usedforsecurity=False,
        ).hexdigest()[:10]

        return f"{safe_stem}-{digest}{safe_suffix}"

    def _rewrite_image_value(
        self,
        value: str,
        base_url: str = "",
        images_prefix: str = "Images",
    ) -> tuple[str, str | None]:
        normalized = self._normalize_asset_url(base_url, value)

        if normalized == "":
            return value, None

        filename = self.image_filename_from_url(normalized)
        if not filename:
            return value, None

        prefix = str(images_prefix or "Images").strip().rstrip("/")
        rewritten = f"{prefix}/{filename}" if prefix else filename
        return rewritten, normalized

    def _rewrite_srcset_value(
        self,
        srcset: str,
        base_url: str = "",
        images_prefix: str = "Images",
    ) -> tuple[str, list[str]]:
        rewritten_parts: list[str] = []
        originals: list[str] = []

        for part in (item.strip() for item in srcset.split(",")):
            if not part:
                continue

            pieces = part.split()
            source = pieces[0]
            descriptor = " ".join(pieces[1:]) if len(pieces) > 1 else ""

            rewritten_source, original = self._rewrite_image_value(
                source, base_url, images_prefix
            )

            if original:
                originals.append(original)

            rewritten = f"{rewritten_source} {descriptor}".strip()
            rewritten_parts.append(rewritten)

        if not rewritten_parts:
            return srcset, originals
        return ", ".join(rewritten_parts), originals

    def _first_srcset_candidate(self, srcset: str) -> str:
        if not srcset:
            return ""
        first_part = srcset.split(",", 1)[0].strip()
        if not first_part:
            return ""
        return first_part.split()[0]

    def _normalize_asset_url(self, base_url: str, asset_url: str) -> str:
        value = str(asset_url or "").strip()
        if not value or value.startswith("data:"):
            return ""

        if value.startswith("//"):
            return f"https:{value}"
        if value.startswith(("http://", "https://")):
            return value
        if value.startswith("/"):
            return f"{config.BASE_URL.rstrip('/')}{value}"

        if base_url:
            return urljoin(base_url, value)
        return value

    def _rewrite_href(self, href: str, book_id: str) -> str:
        value = (href or "").strip()
        if not value:
            return value

        lower_value = value.lower()
        if lower_value.startswith(
            ("mailto:", "tel:", "javascript:", "data:")
        ) or value.startswith("//"):
            return value

        parsed = urlparse(value)

        if parsed.scheme in {"http", "https"}:
            if not book_id or book_id not in parsed.path:
                return value
            relative_path = self._extract_book_relative_path(parsed.path, book_id)
            if relative_path is None:
                return value

            final_path = self._replace_html_extension(relative_path)
            return urlunparse(
                ("", "", final_path, parsed.params, parsed.query, parsed.fragment)
            )

        if parsed.scheme:
            return value

        relative_path = parsed.path
        if relative_path.startswith("/"):
            extracted = self._extract_book_relative_path(relative_path, book_id)
            if extracted is not None:
                relative_path = extracted

        final_path = self._replace_html_extension(relative_path)
        return urlunparse(
            ("", "", final_path, parsed.params, parsed.query, parsed.fragment)
        )

    def _extract_book_relative_path(self, path: str, book_id: str) -> str | None:
        if not path or not book_id:
            return None

        normalized = path.lstrip("/")
        marker = f"{book_id}/"
        if marker in normalized:
            relative = normalized.split(marker, 1)[1]
            if relative.startswith("-/"):
                relative = relative[2:]
            return relative

        if normalized.endswith(book_id):
            return ""

        return None

    def _replace_html_extension(self, path: str) -> str:
        if not path:
            return path
        if path.lower().endswith(".html"):
            return path[:-5] + ".xhtml"
        return path

    def _sanitize_title(self, title: str) -> str:
        normalized = " ".join(str(title or "").split())
        cleaned = self._CONTROL_CHAR_RE.sub("", normalized)
        return html_lib.escape(cleaned)

    def _sanitize_processed_html(self, html_fragment: str) -> str:
        return self._cleaner.clean(html_fragment)

    def _is_allowed_attribute(self, tag: str, name: str, value: str) -> bool:
        tag_name = (tag or "").lower()
        attr_name = (name or "").lower()
        attr_value = str(value or "")

        if attr_name.startswith("on"):
            return False

        if attr_name in {"href", "src", "data-src"}:
            safe_attr = "src" if attr_name == "data-src" else attr_name
            if not self._is_safe_url(attr_value, tag_name, safe_attr):
                return False

        if attr_name in {"srcset", "data-srcset"}:
            if not self._is_safe_srcset(attr_value, tag_name):
                return False

        if attr_name.startswith(("data-", "aria-")):
            return True

        if attr_name in self._GLOBAL_ALLOWED_ATTRIBUTES:
            return True

        return attr_name in self._TAG_ALLOWED_ATTRIBUTES.get(tag_name, frozenset())

    def _is_safe_srcset(self, srcset: str, tag_name: str) -> bool:
        if not srcset:
            return False

        candidates = [item.strip() for item in srcset.split(",")]
        non_empty_candidates = [candidate for candidate in candidates if candidate]
        if not non_empty_candidates:
            return False

        for candidate in non_empty_candidates:
            parts = candidate.split()
            source = parts[0]
            descriptors = parts[1:]

            if not self._is_safe_url(source, tag_name, "src"):
                return False

            for descriptor in descriptors:
                if not self._SRCSET_DESCRIPTOR_RE.match(descriptor):
                    return False

        return True

    def _is_safe_url(self, value: str, tag_name: str, attr_name: str) -> bool:
        candidate = str(value or "").strip()
        if not candidate:
            return False
        if candidate.startswith(("#", "//")):
            return True

        parsed = urlparse(candidate)
        scheme = (parsed.scheme or "").lower()

        if not scheme:
            return True

        if scheme not in self._ALLOWED_PROTOCOLS:
            return False

        if attr_name == "href":
            return scheme in {"http", "https", "mailto", "tel"}

        if attr_name == "src":
            if scheme == "data":
                return tag_name in {"img", "source"} and candidate.lower().startswith(
                    "data:image/"
                )
            return scheme in {"http", "https"}

        return True

    def detect_cover_image(self, soup: Tag) -> str | None:
        for img in soup.find_all("img"):
            src = img.get("src", "")
            alt = img.get("alt", "")
            img_id = img.get("id", "")
            img_class = " ".join(img.get("class", []))

            if any(
                _COVER_WORD_RE.search(value) for value in (src, alt, img_id, img_class)
            ):
                return img.get("src")

        for div in soup.find_all("div"):
            div_id = div.get("id", "")
            div_class = " ".join(div.get("class", []))

            if _COVER_WORD_RE.search(div_id) or _COVER_WORD_RE.search(div_class):
                img = div.find("img")
                if img:
                    return img.get("src")

        return None
