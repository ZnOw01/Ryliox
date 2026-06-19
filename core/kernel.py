"""Microkernel: owns the HTTP client and the registry of plugins."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

from .http_client import HttpClient


class Kernel:
    """The microkernel.

    The kernel owns the shared :class:`HttpClient` and a registry of plugins.
    Plugins access the HTTP client via :attr:`self.kernel.http` (or
    :attr:`self.http` directly, set by :meth:`register`).

    The kernel itself is an async context manager that owns the underlying
    HTTP client. Accessing ``kernel.http`` before entering the context
    raises :class:`RuntimeError`. Accessing ``kernel.http_client`` returns a
    lightweight stub for environments that don't need real HTTP.
    """

    def __init__(self, http: HttpClient | None = None) -> None:
        self._http: HttpClient | None = http
        self._owns_http: bool = http is not None
        self._plugins: dict[str, Any] = {}
        self._entered: bool = False

    # ---- context manager ------------------------------------------------

    async def __aenter__(self) -> Kernel:
        if self._http is None:
            self._http = HttpClient()
            self._owns_http = True
        await self._http.__aenter__()
        self._entered = True
        for plugin in self._plugins.values():
            plugin.kernel = self
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._http is not None and self._owns_http:
            await self._http.close()
        self._entered = False

    # ---- http accessors -------------------------------------------------

    @property
    def http(self) -> HttpClient:
        """Return the configured HTTP client.

        Raises :class:`RuntimeError` if accessed before the kernel has been
        entered via ``async with``. This prevents code from accidentally
        using an uninitialised client.
        """
        if self._http is None or not self._entered:
            raise RuntimeError(
                "Kernel HTTP client is not initialized — use 'async with create_default_kernel() as kernel'"
            )
        return self._http

    @property
    def http_client(self) -> HttpClient | None:
        """Return the HTTP client without raising, or ``None`` if not set up.

        Useful for plugins that want to gracefully skip HTTP work in tests.
        """
        return self._http

    # ---- plugin registry ------------------------------------------------

    def register(self, name: str, plugin: Any) -> None:
        plugin.kernel = self
        self._plugins[name] = plugin

    def get(self, name: str) -> Any | None:
        return self._plugins.get(name)

    def __getitem__(self, name: str) -> Any:
        return self._plugins[name]

    def __contains__(self, name: str) -> bool:
        return name in self._plugins

    def __iter__(self) -> Iterator[str]:
        return iter(self._plugins)


async def create_default_kernel() -> Kernel:
    """Create a kernel with all standard plugins registered.

    Returns a :class:`Kernel` ready to be used as ``async with await
    create_default_kernel() as kernel:``. The kernel is not yet entered,
    so calling ``kernel.http`` outside the context raises.
    """
    from plugins import (
        AssetsPlugin,
        AuthPlugin,
        BookPlugin,
        ChaptersPlugin,
        DownloaderPlugin,
        EpubPlugin,
        HtmlProcessorPlugin,
        OutputPlugin,
        PdfPlugin,
        SystemPlugin,
        TokenPlugin,
    )

    kernel = Kernel()

    # Core plugins
    kernel.register("auth", AuthPlugin())
    kernel.register("book", BookPlugin())
    kernel.register("chapters", ChaptersPlugin())
    kernel.register("assets", AssetsPlugin())
    kernel.register("html_processor", HtmlProcessorPlugin())

    # Output format plugins
    kernel.register("epub", EpubPlugin())
    kernel.register("pdf", PdfPlugin())
    kernel.register("token", TokenPlugin())

    # Orchestration & system plugins
    kernel.register("output", OutputPlugin())
    kernel.register("system", SystemPlugin())
    kernel.register("downloader", DownloaderPlugin())

    return kernel
