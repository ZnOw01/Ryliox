from __future__ import annotations

import pytest

from plugins.html_processor import HtmlProcessorPlugin

pytestmark = pytest.mark.unit


def test_image_filename_from_url_generates_stable_safe_name():
    plugin = HtmlProcessorPlugin()

    filename = plugin.image_filename_from_url(
        "https://learning.oreilly.com/assets/My Cover Image!!.png?size=large"
    )

    assert filename is not None
    assert filename.endswith(".png")
    assert " " not in filename
    assert "!" not in filename
    assert filename.startswith("My_Cover_Image-")


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("es", "es"),
        ("pt_BR", "pt-BR"),
        ("zh-Hant-TW", "zh-Hant-TW"),
        ("", "en"),
        ('x" onload="', "en"),
    ],
)
def test_wrap_xhtml_declares_the_book_language(language: str, expected: str):
    wrapped = HtmlProcessorPlugin().wrap_xhtml("<p>Hola</p>", [], "T", language=language)

    assert f'lang="{expected}" xml:lang="{expected}"' in wrapped


def test_wrap_xhtml_escapes_title_and_includes_stylesheets():
    plugin = HtmlProcessorPlugin()

    wrapped = plugin.wrap_xhtml(
        "<p>Hello</p>",
        ["Styles/base.css", "Styles/theme.css"],
        title='Demo <Book> "Title"',
    )

    assert '<?xml version="1.0" encoding="utf-8"?>' in wrapped
    assert "<title>Demo &lt;Book&gt; &quot;Title&quot;</title>" in wrapped
    assert '<link href="Styles/base.css" rel="stylesheet" type="text/css"/>' in wrapped
    assert '<link href="Styles/theme.css" rel="stylesheet" type="text/css"/>' in wrapped
    assert "<p>Hello</p>" in wrapped


def test_rewrite_srcset_value_rewrites_each_candidate():
    plugin = HtmlProcessorPlugin()

    rewritten, originals = plugin._rewrite_srcset_value(
        "/images/cover.png 1x, https://learning.oreilly.com/assets/hero.jpg 2x",
        base_url="https://learning.oreilly.com/library/view/demo/ch1.xhtml",
    )

    assert "Images/" in rewritten
    assert rewritten.endswith("2x")
    assert originals == [
        "https://learning.oreilly.com/images/cover.png",
        "https://learning.oreilly.com/assets/hero.jpg",
    ]


def test_rewrite_image_value_downloads_all_images_for_offline_epub():
    plugin = HtmlProcessorPlugin()

    rewritten, original = plugin._rewrite_image_value(
        "https://example.com/cover.png",
        base_url="https://learning.oreilly.com/library/view/demo/ch1.xhtml",
    )

    # All images are rewritten to Images/ for self-contained offline EPUB
    assert rewritten.startswith("Images/")
    assert rewritten.endswith(".png")
    # Original URL is preserved for download queue
    assert original == "https://example.com/cover.png"


def test_rewrite_href_rewrites_chapter_paths_to_local_xhtml():
    plugin = HtmlProcessorPlugin()

    href = plugin._rewrite_href(
        "https://example.com/library/view/9781098181642/ch1.html",
        "9781098181642",
    )

    # Chapter hrefs are converted to local .xhtml references for EPUB navigation
    assert href == "ch1.xhtml"


@pytest.mark.parametrize(
    "src",
    [
        "https://learning.oreilly.com/api/v2/epubs/urn:orm:book:1/files/fig 1.png",
        "https://learning.oreilly.com/library/cover/1/fig.png?size=large",
        "assets/fig(1).png",
    ],
)
def test_rewritten_image_src_names_the_file_the_assets_plugin_saves(src):
    from plugins.assets import AssetsPlugin

    content, images = HtmlProcessorPlugin().process(
        f'<div id="sbo-rt-content"><img src="{src}"/></div>', "1"
    )

    assert images == [src]
    assert f'src="Images/{AssetsPlugin._filename_from_url(src)}"' in content


def test_process_gives_every_image_an_alt():
    page = (
        '<div id="sbo-rt-content"><img src="/a/logo.jpg"/>'
        '<img alt="Diagram" src="/a/fig.png"/>'
        '<svg width="10" height="10"><image href="/a/art.png"/></svg></div>'
    )

    content, _ = HtmlProcessorPlugin().process(page, "9781")

    assert '<img alt="" src="Images/logo.jpg"/>' in content
    assert 'alt="Diagram"' in content
    assert content.count("alt=") == 3
