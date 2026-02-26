"""Core package exports with lazy imports."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "Kernel",
    "create_default_kernel",
    "HttpClient",
    "ChapterInfo",
    "ChapterSummary",
    "BookInfo",
    "FormatInfo",
    "process_manager",
]


def __getattr__(name: str) -> Any:
    if name in {"Kernel", "create_default_kernel"}:
        module = import_module(".kernel", __name__)
        return getattr(module, name)

    if name == "HttpClient":
        module = import_module(".http_client", __name__)
        return module.HttpClient

    if name in {"ChapterInfo", "ChapterSummary", "BookInfo", "FormatInfo"}:
        module = import_module(".types", __name__)
        return getattr(module, name)

    if name == "process_manager":
        return import_module(".process_manager", __name__)

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
