"""Local filesystem adapter implementing the ProjectFiles protocol."""

from __future__ import annotations

import os
from pathlib import Path, PurePath
from typing import TYPE_CHECKING, Literal, TypeAlias

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from tingle.pacts.metrics import UnreachableDir

#: What an entry is, as far as the walk is concerned. The empty string is
#: everything else: a socket, a broken link, an entry that went away
#: mid-walk -- anything there is neither to descend into nor to measure.
_Kind: TypeAlias = Literal["directory", "file", ""]


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

    def walk(self) -> Iterator[PurePath]:
        """Yield every file under the root, as a relative path, as it is found.

        Lazily, and so in no particular order: the caller counting the
        walk is the loading screen, and a tree is the one part of a run
        whose size is unknown until it ends. Sorting here would drain the
        whole tree before the first path came back, leaving that screen
        with nothing to say for exactly as long as the walk takes.

        `scandir` rather than `rglob`, because a directory entry already
        knows whether it is a directory: `rglob` builds a `Path` per entry
        and stats every one of them, which on a tree carrying a virtualenv
        is most of what a run spends its time on.

        The two symlink rules are rglob's, kept so that swapping the walk
        cannot change which files a metric sees: a link to a directory is
        not descended into, so a cycle cannot hang the walk, while a link
        to a file is followed and counts as the file it points at.
        """
        root = PurePath()
        stack = [(str(self._root), root)]
        while stack:
            directory, relative = stack.pop()
            at_root = relative == root
            for entry in _listing(directory):
                kind = _kind(entry)
                if kind == "directory" and not self._prunes(
                    entry.name, at_root=at_root
                ):
                    stack.append((entry.path, relative / entry.name))
                elif kind == "file":
                    yield relative / entry.name

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

    Read to the end rather than yielded through, so that handing a path
    back does not hold a directory open for as long as the caller takes
    to use it: a scandir iterator closes itself once exhausted, and
    `list` is what exhausts it.

    Skipping an unreadable directory rather than failing on it is what
    rglob did, and a source tree is exactly where one turns up.
    """
    try:
        return list(os.scandir(directory))
    except OSError:
        return []


def _kind(entry: os.DirEntry[str]) -> _Kind:
    """Say what the walk does with one entry, in a single guarded look.

    One `try` around both questions because they fail together: whatever
    makes an entry unreadable -- it went away mid-walk, it is a link that
    points at itself -- leaves neither of them answerable, and an entry
    nobody can classify is one to leave alone.
    """
    try:
        return (
            "directory"
            if entry.is_dir(follow_symlinks=False)
            else "file" if entry.is_file() else ""
        )
    except OSError:
        return ""
