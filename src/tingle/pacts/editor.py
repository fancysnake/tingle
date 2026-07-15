"""The contract for opening a located hit in the user's editor."""

from __future__ import annotations

from abc import abstractmethod
from typing import Protocol


class EditorOpener(Protocol):
    """Opens a file, optionally at a line, in whatever editor is reachable."""

    @property
    @abstractmethod
    def available(self) -> bool:
        """Whether anything can be opened at all in this environment."""

    @abstractmethod
    def open(self, path: str, line: int | None) -> None:
        """Open `path` (at `line`, when given). Called only when available."""
