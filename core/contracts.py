"""Types shared between the plugins and the download queue."""

from typing import TypedDict


class DownloadCancelledError(Exception):
    """Raised when a download job is cancelled by user request."""


class ChapterInfo(TypedDict):
    """Full chapter metadata returned by ChaptersPlugin.fetch_list()."""

    ourn: str
    title: str
    filename: str
    content_url: str
    images: list[str]
    stylesheets: list[str]
    virtual_pages: int | None
    minutes_required: float | None
