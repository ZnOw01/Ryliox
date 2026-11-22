from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from plugins.assets import AssetsPlugin

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_download_all_images_uses_urlparse_to_derive_filename(tmp_path: Path):
    plugin = AssetsPlugin()

    async def fake_download(_url: str, save_path: Path) -> Path:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(b"ok")
        return save_path

    plugin.download_image = fake_download  # type: ignore[method-assign]

    result = await plugin.download_all_images(
        ["https://example.com/assets/cover.png?size=large"],
        tmp_path,
    )

    saved_path = result["https://example.com/assets/cover.png?size=large"]
    assert saved_path == tmp_path / "Images" / "cover.png"
    assert saved_path.read_bytes() == b"ok"


@pytest.mark.asyncio
async def test_download_all_images_records_canonical_returned_path(tmp_path: Path):
    plugin = AssetsPlugin()

    async def fake_download(_url: str, save_path: Path) -> Path:
        canonical_path = save_path.with_suffix(".png")
        canonical_path.parent.mkdir(parents=True, exist_ok=True)
        canonical_path.write_bytes(b"png")
        return canonical_path

    plugin.download_image = fake_download  # type: ignore[method-assign]

    result = await plugin.download_all_images(
        ["https://example.com/assets/cover.bin"],
        tmp_path,
    )

    assert result["https://example.com/assets/cover.bin"] == tmp_path / "Images" / "cover.png"
    assert result["https://example.com/assets/cover.bin"].is_file()


@pytest.mark.asyncio
async def test_download_css_assets_blocks_path_traversal(tmp_path: Path):
    plugin = AssetsPlugin()
    oebps = tmp_path / "OEBPS"
    styles = oebps / "Styles"
    styles.mkdir(parents=True)
    (styles / "Style00.css").write_text(
        "body{background:url('../Images/escape.png')} .ok{background:url('safe.png')}",
        encoding="utf-8",
    )

    async def fake_download(_url: str, save_path: Path) -> bool:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(b"ok")
        return True

    plugin.download_image = fake_download  # type: ignore[method-assign]

    await plugin.download_css_assets(["https://learning.oreilly.com/book/style.css"], oebps)

    assert not (oebps / "Images" / "escape.png").exists()
    assert (styles / "safe.png").read_bytes() == b"ok"
