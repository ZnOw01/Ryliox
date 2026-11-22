from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from plugins.downloader import DownloaderPlugin

pytestmark = pytest.mark.unit

STAGING_DIRNAME = ".ryliox-staging"


def _chapter(filename: str, title: str) -> dict[str, str]:
    return {
        "title": title,
        "filename": filename,
        "content_url": f"https://learning.oreilly.com/{filename}",
        "images": [],
        "stylesheets": [],
    }


class DummyBookPlugin:
    async def fetch(self, _book_id: str) -> dict[str, object]:
        return {"title": "Demo", "authors": ["Author"]}


class DummyBookWithCoverPlugin:
    async def fetch(self, _book_id: str) -> dict[str, object]:
        return {
            "title": "Demo",
            "authors": ["Author"],
            "cover_url": "https://learning.oreilly.com/library/cover/demo-book/",
        }


class DummyChaptersPlugin:
    def __init__(self, chapters: list[dict[str, str]] | None = None) -> None:
        self._chapters = (
            chapters if chapters is not None else [_chapter("chapter-1.html", "Chapter 1")]
        )

    async def fetch_list(self, _book_id: str) -> list[dict[str, str]]:
        return self._chapters

    async def fetch_toc(self, _book_id: str) -> list[dict[str, str]]:
        return []

    async def fetch_content(self, _content_url: str) -> str:
        return "<p>Chapter body</p>"


class DummyOutputPlugin:
    def create_book_dir(self, **_kwargs):
        raise AssertionError("create_book_dir should not be called for invalid selection")


class DummyEmptyChaptersPlugin:
    async def fetch_list(self, _book_id: str) -> list[dict[str, str]]:
        return []

    async def fetch_toc(self, _book_id: str) -> list[dict[str, str]]:
        return []


class DummySuccessfulOutputPlugin:
    def create_book_dir(self, output_dir: Path, **_kwargs):
        book_dir = output_dir / "demo-book"
        (book_dir / "OEBPS").mkdir(parents=True)
        return book_dir

    def get_oebps_dir(self, book_dir: Path) -> Path:
        return book_dir / "OEBPS"

    def get_images_dir(self, book_dir: Path) -> Path:
        return book_dir / "OEBPS" / "Images"


class DummyAssetsWithDetectedCoverPlugin:
    async def download_image(self, _url: str, save_path: Path) -> Path:
        cover_path = save_path.with_suffix(".jpg")
        cover_path.parent.mkdir(parents=True, exist_ok=True)
        cover_path.write_bytes(b"fake-jpeg")
        return cover_path

    async def download_all_css(self, *_args, **_kwargs) -> dict[str, Path]:
        return {}

    async def download_css_assets(self, *_args, **_kwargs) -> None:
        return None

    async def download_all_images(self, *_args, **_kwargs) -> dict[str, Path]:
        return {}


class DummyHtmlProcessorPlugin:
    def inline_css_content_images(self, _oebps: Path) -> None:
        return None


class DummyFullHtmlProcessorPlugin:
    def process(
        self,
        html: str,
        _book_id: str,
        skip_images: bool = False,
        path_prefix: str = "",
    ) -> tuple[str, list[str]]:
        return html, []

    def wrap_xhtml(self, content: str, _css_files: list[str], title: str = "") -> str:
        return f"<html><head><title>{title}</title></head><body>{content}</body></html>"

    def inline_css_content_images(self, _oebps: Path) -> None:
        return None


class DummyFullAssetsPlugin:
    async def download_image(self, _url: str, save_path: Path) -> Path:
        cover_path = save_path.with_suffix(".jpg")
        cover_path.parent.mkdir(parents=True, exist_ok=True)
        cover_path.write_bytes(b"fake-jpeg")
        return cover_path

    async def download_all_css(self, *_args, **_kwargs) -> dict[str, Path]:
        return {}

    async def download_css_assets(self, *_args, **_kwargs) -> None:
        return None

    async def download_all_images(self, *_args, **_kwargs) -> dict[str, Path]:
        return {}


class FailingCssAssetsPlugin:
    async def download_all_css(self, *_args, **_kwargs) -> dict[str, Path]:
        raise RuntimeError("css download failed")

    async def download_css_assets(self, *_args, **_kwargs) -> None:
        return None

    async def download_all_images(self, *_args, **_kwargs) -> dict[str, Path]:
        return {}


class DummyEpubPlugin:
    def __init__(self) -> None:
        self.cover_image: str | None = None

    def generate(self, *, output_dir: Path, cover_image: str | None = None, **_kwargs) -> Path:
        self.cover_image = cover_image
        epub_path = output_dir / "demo.epub"
        epub_path.write_text("epub", encoding="utf-8")
        return epub_path


class FailingEpubPlugin:
    def generate(self, **_kwargs) -> Path:
        raise RuntimeError("epub generation failed")


class OutsideEpubPlugin:
    def __init__(self, outside_path: Path) -> None:
        self.outside_path = outside_path

    def generate(self, **_kwargs) -> Path:
        self.outside_path.write_text("foreign", encoding="utf-8")
        return self.outside_path


class FakeStagedOutputPlugin:
    def __init__(self) -> None:
        self.created_staging: list[Path] = []
        self.cleaned_staging: list[Path] = []
        self.published: list[Path] = []

    def create_book_dir(self, output_dir: Path, book_id: str, **_kwargs) -> Path:
        book_dir = output_dir / "demo-book"
        (book_dir / "OEBPS").mkdir(parents=True)
        (book_dir / ".book_id").write_text(book_id)
        return book_dir

    def get_oebps_dir(self, book_dir: Path) -> Path:
        return book_dir / "OEBPS"

    def get_images_dir(self, book_dir: Path) -> Path:
        return book_dir / "OEBPS" / "Images"

    def create_staging_dir(self, output_dir: Path, job_id: str) -> Path:
        staging_root = output_dir / STAGING_DIRNAME
        staging_root.mkdir(parents=True, exist_ok=True)
        candidate = staging_root / job_id
        counter = 2
        while candidate.exists():
            candidate = staging_root / f"{job_id}-{counter}"
            counter += 1
        candidate.mkdir()
        self.created_staging.append(candidate)
        return candidate

    def publish_staged_dir(self, staged_book_dir: Path, output_dir: Path, _book_id: str) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / staged_book_dir.name
        counter = 2
        while target.exists():
            target = output_dir / f"{staged_book_dir.name}-{counter}"
            counter += 1
        staged_book_dir.replace(target)
        self.published.append(target)
        return target

    def cleanup_staging(self, staging_dir: Path) -> None:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        self.cleaned_staging.append(staging_dir)


class CleanupFailingAfterPublishOutputPlugin(FakeStagedOutputPlugin):
    def cleanup_staging(self, staging_dir: Path) -> None:
        if self.published:
            raise OSError("simulated cleanup failure after publication")
        super().cleanup_staging(staging_dir)


class CheckpointCanceller:
    def __init__(self, cancel_on: int) -> None:
        self.cancel_on = cancel_on
        self.calls = 0

    def __call__(self) -> bool:
        self.calls += 1
        return self.calls == self.cancel_on


def test_normalize_asset_url_blocks_external_hosts():
    plugin = DownloaderPlugin()

    assert plugin._normalize_asset_url("", "https://example.com/file.png") == ""


def test_normalize_asset_url_allows_subdomains_of_base_host():
    plugin = DownloaderPlugin()

    assert (
        plugin._normalize_asset_url("", "https://cdn.learning.oreilly.com/assets/file.png")
        == "https://cdn.learning.oreilly.com/assets/file.png"
    )


@pytest.mark.asyncio
async def test_download_rejects_epub_chapter_selection_before_creating_output_dir():
    plugin = DownloaderPlugin(
        book_plugin=DummyBookPlugin(),
        chapters_plugin=DummyChaptersPlugin(),
        assets_plugin=object(),
        html_processor_plugin=object(),
        output_plugin=DummyOutputPlugin(),
        epub_plugin=object(),
    )

    with pytest.raises(ValueError, match="Chapter selection not supported for: epub"):
        await plugin.download(
            book_id="demo-book",
            output_dir=Path("/tmp/demo-output"),
            formats=["epub"],
            selected_chapters=[0],
            skip_images=True,
        )


@pytest.mark.asyncio
async def test_download_raises_when_selected_chapters_do_not_match():
    plugin = DownloaderPlugin(
        book_plugin=DummyBookPlugin(),
        chapters_plugin=DummyChaptersPlugin(),
        assets_plugin=object(),
        html_processor_plugin=object(),
        output_plugin=DummyOutputPlugin(),
        epub_plugin=object(),
    )

    with pytest.raises(ValueError, match="Selected chapters did not match"):
        await plugin.download(
            book_id="demo-book",
            output_dir=Path("/tmp/demo-output"),
            formats=["pdf-chapters"],
            selected_chapters=[99],
            skip_images=True,
        )


def test_get_formats_info_hides_redundant_pdf_chapters_option_from_ui():
    formats_info = DownloaderPlugin.get_formats_info()

    assert formats_info["formats"] == ["epub", "pdf"]
    assert "pdf-chapters" in formats_info["descriptions"]
    assert set(formats_info["descriptions"]) == {"epub", "pdf", "pdf-chapters"}


@pytest.mark.asyncio
async def test_download_passes_detected_cover_filename_to_epub(tmp_path):
    epub_plugin = DummyEpubPlugin()
    plugin = DownloaderPlugin(
        book_plugin=DummyBookWithCoverPlugin(),
        chapters_plugin=DummyEmptyChaptersPlugin(),
        assets_plugin=DummyAssetsWithDetectedCoverPlugin(),
        html_processor_plugin=DummyHtmlProcessorPlugin(),
        output_plugin=DummySuccessfulOutputPlugin(),
        epub_plugin=epub_plugin,
    )

    await plugin.download(
        book_id="demo-book",
        output_dir=tmp_path,
        formats=["epub"],
        skip_images=False,
    )

    assert epub_plugin.cover_image == "cover.jpg"


@pytest.mark.asyncio
async def test_download_success_publishes_complete_book_from_staging(tmp_path: Path):
    output_plugin = FakeStagedOutputPlugin()
    progress_statuses: list[str] = []
    plugin = DownloaderPlugin(
        book_plugin=DummyBookPlugin(),
        chapters_plugin=DummyChaptersPlugin(),
        assets_plugin=DummyFullAssetsPlugin(),
        html_processor_plugin=DummyFullHtmlProcessorPlugin(),
        output_plugin=output_plugin,
        epub_plugin=DummyEpubPlugin(),
    )

    result = await plugin.download(
        book_id="demo-book",
        output_dir=tmp_path,
        formats=["epub"],
        skip_images=True,
        job_id="job-abc",
        progress_callback=lambda progress: progress_statuses.append(progress.status),
    )

    assert output_plugin.created_staging == [tmp_path / STAGING_DIRNAME / "job-abc"]
    assert result.output_dir == tmp_path / "demo-book"
    assert result.files["epub"] == str(tmp_path / "demo-book" / "demo.epub")
    assert (tmp_path / "demo-book" / "demo.epub").is_file()
    assert (tmp_path / "demo-book" / "OEBPS" / "chapter-1.xhtml").is_file()
    assert (tmp_path / "demo-book" / ".book_id").read_text() == "demo-book"
    assert output_plugin.cleaned_staging == output_plugin.created_staging
    assert (tmp_path / STAGING_DIRNAME).is_dir()
    assert not any((tmp_path / STAGING_DIRNAME).iterdir())
    assert "finalizing" in progress_statuses
    assert "completed" not in progress_statuses


@pytest.mark.asyncio
async def test_post_publish_cleanup_failure_does_not_fail_completed_download(tmp_path: Path):
    output_plugin = CleanupFailingAfterPublishOutputPlugin()
    plugin = DownloaderPlugin(
        book_plugin=DummyBookPlugin(),
        chapters_plugin=DummyChaptersPlugin(),
        assets_plugin=DummyFullAssetsPlugin(),
        html_processor_plugin=DummyFullHtmlProcessorPlugin(),
        output_plugin=output_plugin,
        epub_plugin=DummyEpubPlugin(),
    )

    result = await plugin.download(
        book_id="demo-book",
        output_dir=tmp_path,
        formats=["epub"],
        skip_images=True,
        job_id="job-cleanup-failure",
    )

    assert result.output_dir == tmp_path / "demo-book"
    assert (result.output_dir / "demo.epub").is_file()


@pytest.mark.asyncio
async def test_download_uses_provided_job_id_for_staging(tmp_path: Path):
    output_plugin = FakeStagedOutputPlugin()
    plugin = DownloaderPlugin(
        book_plugin=DummyBookPlugin(),
        chapters_plugin=DummyChaptersPlugin(),
        assets_plugin=DummyFullAssetsPlugin(),
        html_processor_plugin=DummyFullHtmlProcessorPlugin(),
        output_plugin=output_plugin,
        epub_plugin=DummyEpubPlugin(),
    )

    await plugin.download(
        book_id="demo-book",
        output_dir=tmp_path,
        formats=["epub"],
        skip_images=True,
        job_id="custom-job-123",
    )

    assert output_plugin.created_staging == [tmp_path / STAGING_DIRNAME / "custom-job-123"]


@pytest.mark.asyncio
async def test_download_generates_secure_job_token_when_job_id_omitted(tmp_path: Path):
    output_plugin = FakeStagedOutputPlugin()
    plugin = DownloaderPlugin(
        book_plugin=DummyBookPlugin(),
        chapters_plugin=DummyChaptersPlugin(),
        assets_plugin=DummyFullAssetsPlugin(),
        html_processor_plugin=DummyFullHtmlProcessorPlugin(),
        output_plugin=output_plugin,
        epub_plugin=DummyEpubPlugin(),
    )

    await plugin.download(
        book_id="demo-book",
        output_dir=tmp_path,
        formats=["epub"],
        skip_images=True,
    )

    assert len(output_plugin.created_staging) == 1
    staging_job = output_plugin.created_staging[0]
    assert staging_job.parent.name == STAGING_DIRNAME
    assert staging_job.name
    assert "/" not in staging_job.name
    assert ".." not in staging_job.name


@pytest.mark.asyncio
async def test_download_asset_failure_cleans_staging_without_publishing(tmp_path: Path):
    output_plugin = FakeStagedOutputPlugin()
    plugin = DownloaderPlugin(
        book_plugin=DummyBookPlugin(),
        chapters_plugin=DummyChaptersPlugin(),
        assets_plugin=FailingCssAssetsPlugin(),
        html_processor_plugin=DummyFullHtmlProcessorPlugin(),
        output_plugin=output_plugin,
        epub_plugin=DummyEpubPlugin(),
    )

    with pytest.raises(RuntimeError, match="css download failed"):
        await plugin.download(
            book_id="demo-book",
            output_dir=tmp_path,
            formats=["epub"],
            skip_images=True,
            job_id="job-fail-assets",
        )

    assert output_plugin.published == []
    assert output_plugin.cleaned_staging == output_plugin.created_staging
    assert not (tmp_path / "demo-book").exists()
    assert not (tmp_path / STAGING_DIRNAME / "job-fail-assets").exists()


@pytest.mark.asyncio
async def test_download_format_failure_cleans_staging_without_publishing(tmp_path: Path):
    output_plugin = FakeStagedOutputPlugin()
    plugin = DownloaderPlugin(
        book_plugin=DummyBookPlugin(),
        chapters_plugin=DummyChaptersPlugin(),
        assets_plugin=DummyFullAssetsPlugin(),
        html_processor_plugin=DummyFullHtmlProcessorPlugin(),
        output_plugin=output_plugin,
        epub_plugin=FailingEpubPlugin(),
    )

    with pytest.raises(RuntimeError, match="epub generation failed"):
        await plugin.download(
            book_id="demo-book",
            output_dir=tmp_path,
            formats=["epub"],
            skip_images=True,
            job_id="job-fail-format",
        )

    assert output_plugin.published == []
    assert output_plugin.cleaned_staging == output_plugin.created_staging
    assert not (tmp_path / "demo-book").exists()
    assert not (tmp_path / STAGING_DIRNAME / "job-fail-format").exists()


@pytest.mark.asyncio
async def test_output_path_outside_staged_book_is_rejected_before_publication(tmp_path: Path):
    output_plugin = FakeStagedOutputPlugin()
    foreign = tmp_path / "foreign.epub"
    plugin = DownloaderPlugin(
        book_plugin=DummyBookPlugin(),
        chapters_plugin=DummyChaptersPlugin(),
        assets_plugin=DummyFullAssetsPlugin(),
        html_processor_plugin=DummyFullHtmlProcessorPlugin(),
        output_plugin=output_plugin,
        epub_plugin=OutsideEpubPlugin(foreign),
    )

    with pytest.raises(ValueError):
        await plugin.download(
            book_id="demo-book",
            output_dir=tmp_path,
            formats=["epub"],
            skip_images=True,
            job_id="job-outside-path",
        )

    assert foreign.read_text(encoding="utf-8") == "foreign"
    assert output_plugin.published == []
    assert not (tmp_path / "demo-book").exists()
    assert not (tmp_path / STAGING_DIRNAME / "job-outside-path").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "checkpoint",
    [1, 2, 3, 4, 5],
    ids=["before-write", "before-assets", "after-assets", "before-format", "after-format"],
)
async def test_download_cancel_cleans_staging_and_never_publishes(tmp_path: Path, checkpoint: int):
    output_plugin = FakeStagedOutputPlugin()
    canceller = CheckpointCanceller(checkpoint)
    plugin = DownloaderPlugin(
        book_plugin=DummyBookPlugin(),
        chapters_plugin=DummyChaptersPlugin(),
        assets_plugin=DummyFullAssetsPlugin(),
        html_processor_plugin=DummyFullHtmlProcessorPlugin(),
        output_plugin=output_plugin,
        epub_plugin=DummyEpubPlugin(),
    )

    with pytest.raises(Exception, match="Download cancelled by user"):
        await plugin.download(
            book_id="demo-book",
            output_dir=tmp_path,
            formats=["epub"],
            skip_images=True,
            cancel_check=canceller,
            job_id="job-cancel",
        )

    assert output_plugin.published == []
    assert output_plugin.cleaned_staging == output_plugin.created_staging
    assert not (tmp_path / "demo-book").exists()
    assert not (tmp_path / STAGING_DIRNAME / "job-cancel").exists()


@pytest.mark.asyncio
async def test_download_preserves_foreign_files_in_output(tmp_path: Path):
    foreign_dir = tmp_path / "demo-book"
    foreign_dir.mkdir(parents=True)
    (foreign_dir / "notes.txt").write_text("keep me", encoding="utf-8")
    output_plugin = FakeStagedOutputPlugin()
    plugin = DownloaderPlugin(
        book_plugin=DummyBookPlugin(),
        chapters_plugin=DummyChaptersPlugin(),
        assets_plugin=DummyFullAssetsPlugin(),
        html_processor_plugin=DummyFullHtmlProcessorPlugin(),
        output_plugin=output_plugin,
        epub_plugin=DummyEpubPlugin(),
    )

    result = await plugin.download(
        book_id="demo-book",
        output_dir=tmp_path,
        formats=["epub"],
        skip_images=True,
        job_id="job-foreign",
    )

    assert (tmp_path / "demo-book" / "notes.txt").is_file()
    assert result.output_dir == tmp_path / "demo-book-2"
    assert result.files["epub"] == str(tmp_path / "demo-book-2" / "demo.epub")
    assert (tmp_path / "demo-book-2" / "demo.epub").is_file()


@pytest.mark.asyncio
async def test_download_reports_chapters_count_without_retaining_html(tmp_path: Path):
    chapters = [_chapter("ch1.html", "One"), _chapter("ch2.html", "Two")]
    output_plugin = FakeStagedOutputPlugin()
    plugin = DownloaderPlugin(
        book_plugin=DummyBookPlugin(),
        chapters_plugin=DummyChaptersPlugin(chapters),
        assets_plugin=DummyFullAssetsPlugin(),
        html_processor_plugin=DummyFullHtmlProcessorPlugin(),
        output_plugin=output_plugin,
        epub_plugin=DummyEpubPlugin(),
    )

    result = await plugin.download(
        book_id="demo-book",
        output_dir=tmp_path,
        formats=["epub"],
        skip_images=True,
        job_id="job-count",
    )

    assert result.chapters_count == 2


@pytest.mark.asyncio
async def test_download_without_staging_support_keeps_legacy_direct_write(tmp_path: Path):
    plugin = DownloaderPlugin(
        book_plugin=DummyBookPlugin(),
        chapters_plugin=DummyEmptyChaptersPlugin(),
        assets_plugin=DummyAssetsWithDetectedCoverPlugin(),
        html_processor_plugin=DummyHtmlProcessorPlugin(),
        output_plugin=DummySuccessfulOutputPlugin(),
        epub_plugin=DummyEpubPlugin(),
    )

    result = await plugin.download(
        book_id="demo-book",
        output_dir=tmp_path,
        formats=["epub"],
        skip_images=True,
    )

    assert result.output_dir == tmp_path / "demo-book"
    assert result.files["epub"] == str(tmp_path / "demo-book" / "demo.epub")
    assert (tmp_path / "demo-book" / "demo.epub").is_file()
