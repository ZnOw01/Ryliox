from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

import config
from plugins.assets import AssetsPlugin

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_download_all_images_uses_urlparse_to_derive_filename(tmp_path: Path):
    plugin = AssetsPlugin()

    async def fake_download(_url: str, save_path: Path) -> bool:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(b"ok")
        return True

    plugin.download_image = fake_download  # type: ignore[method-assign]

    result = await plugin.download_all_images(
        ["https://example.com/assets/cover.png?size=large"],
        tmp_path,
    )

    saved_path = result["https://example.com/assets/cover.png?size=large"]
    assert saved_path == tmp_path / "Images" / "cover.png"
    assert saved_path.read_bytes() == b"ok"


def test_ensure_safe_asset_url_blocks_external_hosts():
    plugin = AssetsPlugin()

    with pytest.raises(ValueError, match="Blocked asset host outside allowed hosts"):
        plugin._ensure_safe_asset_url("https://example.com/assets/cover.png")


def test_ensure_safe_asset_url_allows_base_host():
    plugin = AssetsPlugin()

    plugin._ensure_safe_asset_url(f"{config.BASE_URL}/assets/cover.png")


@pytest.mark.asyncio
async def test_download_cover_image_uses_real_media_type_for_extension(tmp_path: Path):
    plugin = AssetsPlugin()

    class DummyHttp:
        async def get(self, _url: str, **_kwargs):
            class Response:
                headers = {"content-type": "image/png"}
                content = b"\x89PNG\r\n\x1a\nrest"

                def raise_for_status(self):
                    return None

            return Response()

    plugin.kernel = type("Kernel", (), {"http": DummyHttp()})()

    result = await plugin.download_cover_image(
        f"{config.BASE_URL}/assets/cover.bin",
        tmp_path,
    )

    assert result.name == "cover.png"
    assert result.read_bytes().startswith(b"\x89PNG")
