"""Base plugin class for the microkernel architecture."""

from abc import ABC
from typing import Any


class Plugin(ABC):
    kernel: Any = None

    @property
    def http(self) -> Any:
        """Return the HTTP client attached to the kernel, or ``None``.

        Defensive: in unit tests the plugin may be wired up with explicit
        dependencies (``self.kernel`` is ``None``) and a non-kernel HTTP
        client is injected via ``plugin.http = ...``. We try the kernel
        first, fall back to an instance attribute, then return ``None``.
        """
        kernel = self.kernel
        if kernel is not None:
            http = getattr(kernel, "http", None)
            if http is not None:
                return http
        return getattr(self, "_http_override", None)
