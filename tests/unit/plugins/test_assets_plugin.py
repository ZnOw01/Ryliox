from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from plugins.assets import AssetsPlugin

pytestmark = pytest.mark.unit


def test_download_all_images_uses_urlparse_to_derive_filename(tmp_path: Path):
    plugin = AssetsPlugin()

    async def fake_download(_url: str, save_path: Path) -> bool:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(b"ok")
        return True

    plugin.download_image = fake_download  # type: ignore[method-assign]

    result = asyncio.run(
        plugin.download_all_images(
            ["https://example.com/assets/cover.png?size=large"],
            tmp_path,
        )
    )

    saved_path = result["https://example.com/assets/cover.png?size=large"]
    assert saved_path == tmp_path / "Images" / "cover.png"
    assert saved_path.read_bytes() == b"ok"
