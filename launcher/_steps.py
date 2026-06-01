"""Step counter for the launcher progress UI."""

from __future__ import annotations


class Steps:
    """Print numbered progress labels.

    The displayed total may be exceeded by the actual count (e.g. when a fast
    path skips a step); in that case ``?`` is shown to avoid claiming an
    exact total that is no longer accurate.
    """

    def __init__(self, total: int) -> None:
        self._total = max(0, int(total))
        self._current = 0

    def next(self, label: str) -> None:
        self._current += 1
        total = str(self._total) if self._current <= self._total else "?"
        print(f"[{self._current}/{total}] {label}")

    def format(self, label: str) -> str:
        """Return the formatted label without printing it."""
        self._current += 1
        total = str(self._total) if self._current <= self._total else "?"
        return f"[{self._current}/{total}] {label}"
