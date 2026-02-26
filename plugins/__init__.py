"""Plugin package exports."""

from .assets import AssetsPlugin
from .auth import AuthPlugin
from .base import Plugin
from .book import BookPlugin
from .chapters import ChaptersPlugin
from .downloader import DownloaderPlugin, DownloadProgress, DownloadResult
from .epub import EpubPlugin
from .html_processor import HtmlProcessorPlugin
from .output import OutputPlugin
from .pdf import PdfPlugin
from .system import SystemPlugin

__all__ = [
    "AssetsPlugin",
    "AuthPlugin",
    "BookPlugin",
    "ChaptersPlugin",
    "DownloaderPlugin",
    "DownloadProgress",
    "DownloadResult",
    "EpubPlugin",
    "HtmlProcessorPlugin",
    "OutputPlugin",
    "PdfPlugin",
    "Plugin",
    "SystemPlugin",
]
