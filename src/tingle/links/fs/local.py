"""Local filesystem adapter implementing the ProjectFiles protocol."""

from __future__ import annotations

import os
from pathlib import Path, PurePath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


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
        return iter(sorted(self._descend()))

    def _descend(self) -> Iterator[PurePath]:
        """Walk the tree from the root, yielding files in no order.

        `scandir` rather than `rglob`, because a directory entry already
        knows whether it is a directory: `rglob` builds a `Path` per entry
        and stats every one of them, which on a tree carrying a virtualenv
        is most of what a run spends its time on.

        The two symlink rules are `rglob`'s, kept so that swapping the
        implementation cannot change which files a metric sees. A link to
        a directory is not descended into, so a cycle cannot hang the
        walk; a link to a file is followed, so it counts as the file it
        points at; and a broken one is neither, so it is skipped.
        """
        stack = [(str(self._root), PurePath())]
        while stack:
            directory, relative = stack.pop()
            for entry in _listing(directory):
                child = relative / entry.name
                if _is_directory(entry):
                    stack.append((entry.path, child))
                elif _is_file(entry):
                    yield child

    def read(self, path: PurePath) -> bytes | None:
        """Return the file's raw bytes, or None if it cannot be read."""
        try:
            return (self._root / path).read_bytes()
        except OSError:
            return None

    def exists(self, path: PurePath) -> bool:
        """Return whether the file exists under the root."""
        return (self._root / path).is_file()


def _listing(directory: str) -> list[os.DirEntry[str]]:
    """Every entry in one directory, or none when it cannot be read.

    Skipping an unreadable directory rather than failing on it is what
    rglob did, and a source tree is exactly where one turns up.
    """
    try:
        return _scanned(directory)
    except OSError:
        return []


def _scanned(directory: str) -> list[os.DirEntry[str]]:
    """Read one directory to the end, closing the scan behind it."""
    with os.scandir(directory) as scan:
        return list(scan)


def _is_directory(entry: os.DirEntry[str]) -> bool:
    """Whether to descend into this entry: a directory, and not a link."""
    try:
        return entry.is_dir(follow_symlinks=False)
    except OSError:
        return False


def _is_file(entry: os.DirEntry[str]) -> bool:
    """Whether this entry is a file, following a link to reach one."""
    try:
        return entry.is_file()
    except OSError:
        return False
