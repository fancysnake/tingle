"""The contract for opening a located hit in the user's editor."""

from __future__ import annotations

from abc import abstractmethod
from typing import Protocol


class EditorError(Exception):
    """The editor was there to talk to and would not open the file.

    Distinct from being unavailable, which `available` answers before
    anything is attempted: this is a reachable editor that failed, and it
    is the caller's to report rather than the adapter's to swallow.
    """


class EditorOpener(Protocol):
    """Opens a file, optionally at a line, in whatever editor is reachable."""

    @property
    @abstractmethod
    def available(self) -> bool:
        """Whether anything can be opened at all in this environment."""

    @abstractmethod
    def open(self, path: str, line: int | None) -> None:
        """Open `path` (at `line`, when given). Called only when available.

        Raises EditorError if the editor could not be reached or did not
        answer. May block, so a caller with an event loop runs it off it.
        """
