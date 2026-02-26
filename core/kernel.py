from .http_client import HttpClient


class Kernel:
    def __init__(self, http: HttpClient | None = None):
        self.http = http or HttpClient()
        self._plugins: dict[str, object] = {}

    def register(self, name: str, plugin):
        plugin.kernel = self
        self._plugins[name] = plugin

    def get(self, name: str):
        return self._plugins.get(name)

    def __getitem__(self, name: str):
        return self._plugins[name]


def create_default_kernel() -> Kernel:
    """Create a kernel with all standard plugins registered."""
    from plugins import (
        AuthPlugin,
        BookPlugin,
        ChaptersPlugin,
        AssetsPlugin,
        HtmlProcessorPlugin,
        EpubPlugin,
        PdfPlugin,
        OutputPlugin,
        SystemPlugin,
        DownloaderPlugin,
    )

    kernel = Kernel()

    auth_plugin = AuthPlugin()
    book_plugin = BookPlugin()
    chapters_plugin = ChaptersPlugin()
    assets_plugin = AssetsPlugin()
    html_processor_plugin = HtmlProcessorPlugin()
    epub_plugin = EpubPlugin()
    pdf_plugin = PdfPlugin()
    output_plugin = OutputPlugin()
    system_plugin = SystemPlugin()
    downloader_plugin = DownloaderPlugin(
        book_plugin=book_plugin,
        chapters_plugin=chapters_plugin,
        assets_plugin=assets_plugin,
        html_processor_plugin=html_processor_plugin,
        output_plugin=output_plugin,
        epub_plugin=epub_plugin,
    )

    kernel.register("auth", auth_plugin)
    kernel.register("book", book_plugin)
    kernel.register("chapters", chapters_plugin)
    kernel.register("assets", assets_plugin)
    kernel.register("html_processor", html_processor_plugin)
    kernel.register("epub", epub_plugin)
    kernel.register("pdf", pdf_plugin)
    kernel.register("output", output_plugin)
    kernel.register("system", system_plugin)
    kernel.register("downloader", downloader_plugin)

    return kernel
