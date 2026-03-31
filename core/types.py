"""Shared type definitions for API contracts.

This module contains TypedDict definitions used for API responses
to provide type safety and documentation for data structures.
"""

from typing import TypedDict


class ChapterInfo(TypedDict):
    """Full chapter metadata returned by ChaptersPlugin.fetch_list().

    Attributes:
        ourn: Unique resource name identifier for the chapter.
        title: Human-readable chapter title.
        filename: File path or reference for the chapter content.
        content_url: URL to fetch the chapter's HTML/XHTML content.
        images: List of image URLs referenced in the chapter.
        stylesheets: List of CSS URLs referenced in the chapter.
        virtual_pages: Optional estimated page count.
        minutes_required: Optional estimated reading time in minutes.
    """

    ourn: str
    title: str
    filename: str
    content_url: str
    images: list[str]
    stylesheets: list[str]
    virtual_pages: int | None
    minutes_required: float | None


class ChapterSummary(TypedDict):
    """Simplified chapter info for client display (e.g., chapter picker UI).

    Attributes:
        index: Zero-based chapter index in the book.
        title: Human-readable chapter title.
        pages: Optional estimated page count.
        minutes: Optional estimated reading time in minutes.
    """

    index: int
    title: str
    pages: int | None
    minutes: float | None


class BookInfo(TypedDict, total=False):
    """Book metadata returned by BookPlugin.fetch().

    All fields are optional (total=False) to allow partial book info
    for compatibility with various data sources.

    Attributes:
        book_id: Unique identifier for the book.
        title: Book title.
        authors: List of author names.
        publisher: Primary publisher name.
        cover_url: URL to the book cover image.
        description: Book synopsis or description.
        isbn: International Standard Book Number.
        topics: List of subject/topic tags.
        pages: Total page count.
    """

    book_id: str
    title: str
    authors: list[str]
    publisher: str
    cover_url: str | None
    description: str
    isbn: str | None
    topics: list[str]
    pages: int | None


class FormatInfo(TypedDict):
    """Format metadata for discovery endpoints.

    Attributes:
        name: Format identifier (e.g., 'epub', 'pdf').
        description: Human-readable format description.
        supports_chapters: Whether the format supports chapter-level selection.
        aliases: List of alternative names for the format.
    """

    name: str
    description: str
    supports_chapters: bool
    aliases: list[str]
