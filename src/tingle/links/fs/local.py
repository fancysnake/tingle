"""Local filesystem adapter implementing the ProjectFiles protocol."""

from __future__ import annotations

from pathlib import Path, PurePath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


class LocalProjectFiles:
    """Read-only view of a local directory tree.

    walk() returns the full tree; which files matter is range logic and
    stays in mills.
    """

    def __init__(self, root: Path) -> None:
        """Anchor the view at the project root directory."""
        self._root = root

    def walk(self) -> Iterable[PurePath]:
        """Yield every file under the root as a sorted relative path."""
        for path in sorted(self._root.rglob("*")):
            if path.is_file():
                yield PurePath(path.relative_to(self._root))

    def read(self, path: PurePath) -> bytes | None:
        """Return the file's raw bytes, or None if it cannot be read."""
        try:
            return (self._root / path).read_bytes()
        except OSError:
            return None

    def exists(self, path: PurePath) -> bool:
        """Return whether the file exists under the root."""
        return (self._root / path).is_file()
