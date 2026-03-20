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


def test_wrap_xhtml_escapes_title_and_includes_stylesheets():
    plugin = HtmlProcessorPlugin()

    wrapped = plugin.wrap_xhtml(
        "<p>Hello</p>",
        ["Styles/base.css", "Styles/theme.css"],
        title='Demo <Book> "Title"',
    )

    assert "<?xml version=\"1.0\" encoding=\"utf-8\"?>" in wrapped
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


def test_rewrite_image_value_keeps_external_images_remote():
    plugin = HtmlProcessorPlugin()

    rewritten, original = plugin._rewrite_image_value(
        "https://example.com/cover.png",
        base_url="https://learning.oreilly.com/library/view/demo/ch1.xhtml",
    )

    assert rewritten == "https://example.com/cover.png"
    assert original is None


def test_rewrite_href_does_not_rewrite_external_hosts_even_with_book_id():
    plugin = HtmlProcessorPlugin()

    href = plugin._rewrite_href(
        "https://example.com/library/view/9781098181642/ch1.html",
        "9781098181642",
    )

    assert href == "https://example.com/library/view/9781098181642/ch1.html"
