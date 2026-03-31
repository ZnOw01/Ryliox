"""Central plugin registry managing HTTP client and plugin lifecycle."""

from .http_client import HttpClient


class Kernel:
    """Central plugin registry managing HTTP client and plugin lifecycle."""

    def __init__(self):
        self._http: HttpClient | None = None
        self._plugins: dict[str, object] = {}

    async def __aenter__(self) -> "Kernel":
        """Async context manager entry - initializes HTTP client."""
        self._http = HttpClient()
        await self._http.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - cleans up HTTP client."""
        if self._http is not None:
            await self._http.__aexit__(exc_type, exc_val, exc_tb)
            self._http = None

    @property
    def http(self) -> HttpClient:
        """Return the HTTP client."""
        if self._http is None:
            raise RuntimeError(
                "Kernel HTTP client not initialized. "
                "Use 'async with kernel:' context manager."
            )
        return self._http

    def register(self, name: str, plugin):
        """Register a plugin under the given name."""
        plugin.kernel = self
        self._plugins[name] = plugin

    def get(self, name: str):
        """Retrieve a plugin by name (returns None if not found)."""
        return self._plugins.get(name)

    def __getitem__(self, name: str):
        """Retrieve a plugin by name (raises KeyError if not found)."""
        return self._plugins[name]


async def create_default_kernel() -> Kernel:
    """Create a kernel with all standard plugins registered.

    Usage:
        async with await create_default_kernel() as kernel:
            # use kernel
    """
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
    await kernel.__aenter__()

    try:
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
    except Exception:
        # Clean up if initialization fails
        await kernel.__aexit__(None, None, None)
        raise
