"""Local filesystem adapter implementing the ProjectFiles protocol."""

from collections.abc import Iterable
from pathlib import Path, PurePath

_BINARY_SNIFF_BYTES = 8192


class LocalProjectFiles:
    """Read-only view of a local directory tree.

    walk() returns the full tree; which files matter is range logic and
    stays in mills.
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    def walk(self) -> Iterable[PurePath]:
        for path in sorted(self._root.rglob("*")):
            if path.is_file():
                yield PurePath(path.relative_to(self._root))

    def read(self, path: PurePath) -> str | None:
        try:
            data = (self._root / path).read_bytes()
        except OSError:
            return None
        if b"\0" in data[:_BINARY_SNIFF_BYTES]:
            return None
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return None

    def exists(self, path: PurePath) -> bool:
        return (self._root / path).is_file()
