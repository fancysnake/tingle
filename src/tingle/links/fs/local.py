"""Local filesystem adapter implementing the ProjectFiles protocol."""

from __future__ import annotations

import os
from enum import Enum, auto
from pathlib import Path, PurePath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

    from tingle.pacts.metrics import UnreachableDir


class _Entry(Enum):
    """What a directory entry is, as far as the walk is concerned."""

    DIRECTORY = auto()
    FILE = auto()
    NEITHER = auto()


class LocalProjectFiles:
    """Read-only view of a local directory tree.

    walk() returns the whole tree bar the directories it is told to skip;
    which files matter is range logic and stays in mills. Those two are
    not the same thing: a skipped directory is one whose contents no range
    could have matched anyway, so the caller is naming work to avoid
    rather than a filter to apply.
    """

    def __init__(self, root: Path, *, prune: Sequence[UnreachableDir] = ()) -> None:
        """Anchor the view at the root, declining to descend into `prune`.

        The two kinds are split apart once here rather than asked about
        per directory: which names are unreachable anywhere, and which
        only as a child of the root.
        """
        self._root = root
        self._anywhere = frozenset(d.name for d in prune if not d.anchored)
        self._at_root = frozenset(d.name for d in prune if d.anchored)

    def walk(self) -> Iterable[PurePath]:
        """Yield every file under the root as a sorted relative path."""
        return iter(sorted(self._descend()))

    def _descend(self) -> Iterator[PurePath]:
        """Walk the tree from the root, yielding files in no order.

        `scandir` rather than `rglob`, because a directory entry already
        knows whether it is a directory: `rglob` builds a `Path` per entry
        and stats every one of them, which on a tree carrying a virtualenv
        is most of what a run spends its time on.

        What counts as a directory to descend and what counts as a file
        to yield is `_reading`'s, which keeps rglob's symlink rules.
        """
        root = PurePath()
        stack = [(str(self._root), root)]
        while stack:
            directory, relative = stack.pop()
            at_root = relative == root
            for entry in _listing(directory):
                child = relative / entry.name
                reading = _reading(entry)
                if reading is _Entry.DIRECTORY and not self._prunes(
                    entry.name, at_root=at_root
                ):
                    stack.append((entry.path, child))
                elif reading is _Entry.FILE:
                    yield child

    def _prunes(self, name: str, *, at_root: bool) -> bool:
        """Whether a directory of this name, at this depth, is unreachable."""
        return name in self._anywhere or (at_root and name in self._at_root)

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


def _reading(entry: os.DirEntry[str]) -> _Entry:
    """Decide what the walk does with one entry, in a single guarded look.

    One `try` around both questions because they fail together: whatever
    makes an entry unreadable -- it went away mid-walk, it is a link that
    points at itself -- leaves neither of them answerable, and an entry
    nobody can classify is one to leave alone.

    The two symlink rules are rglob's, kept so that swapping the walk
    cannot change which files a metric sees: a link to a directory is not
    descended into, so a cycle cannot hang the walk, while a link to a
    file is followed and counts as the file it points at.
    """
    try:
        return _classified(entry)
    except OSError:
        return _Entry.NEITHER


def _classified(entry: os.DirEntry[str]) -> _Entry:
    """Say what the entry is, letting an unreadable one raise."""
    if entry.is_dir(follow_symlinks=False):
        return _Entry.DIRECTORY
    return _Entry.FILE if entry.is_file() else _Entry.NEITHER
