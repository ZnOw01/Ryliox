"""Base plugin class for the microkernel architecture."""

from abc import ABC
from typing import Any


class Plugin(ABC):
    """Base class for plugins registered in the kernel."""

    def __init__(self) -> None:
        self._kernel: Any | None = None

    @property
    def kernel(self) -> Any:
        """Return kernel instance or raise if not configured."""
        if self._kernel is None:
            raise RuntimeError(
                f"Plugin '{self.__class__.__name__}' accessed kernel before registration."
            )
        return self._kernel

    @kernel.setter
    def kernel(self, kernel_instance: Any) -> None:
        """Inject kernel instance into the plugin."""
        self._kernel = kernel_instance

    @property
    def http(self) -> Any:
        """Return kernel HTTP client."""
        if not hasattr(self.kernel, "http"):
            raise RuntimeError("Kernel does not expose an 'http' client.")
        return self.kernel.http

    def setup(self) -> None:
        """Optional hook called after dependency injection."""
        pass
