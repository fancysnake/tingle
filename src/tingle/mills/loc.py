"""Counting the lines a project is made of, once per run.

The size of the codebase is what a metric's debt is read against when it
sets no guide of its own, so it is measured the way `line_count` measures:
every readable file in the range, binary and unreadable ones skipped.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tingle.mills.ranges import resolve

if TYPE_CHECKING:
    from pathlib import PurePath

    from tingle.pacts.config import Config, RangeSpec
    from tingle.pacts.metrics import ProjectFiles


class ProjectLoc:
    """The lines of the loc range, counted once and only when asked.

    Counting means reading the tree, which a config that pins every guide
    has no reason to pay for -- so nothing is read until something needs
    a number, and then it is read once.

    `walked` is the tree the run already walked; it is public because every
    metric resolves its own range against the same walk.
    """

    def __init__(
        self, config: Config, *, project: ProjectFiles, walked: tuple[PurePath, ...]
    ) -> None:
        """Hold what counting will need, without counting anything yet."""
        self._config = config
        self._project = project
        self.walked = walked
        self._lines: int | None = None

    def lines(self) -> int:
        """Total lines of the loc range; counted on the first call only."""
        if self._lines is None:
            self._lines = self._count()
        return self._lines

    def range_spec(self) -> RangeSpec:
        """Return the range LOC is counted over: `loc_range`, else the default.

        A project's default range is already its own statement of what it is
        made of, so it stands in when nothing names another.
        """
        if (name := self._config.display.loc_range) is None:
            return self._config.default_range
        return self._config.ranges[name]

    def _count(self) -> int:
        """Sum the lines of every readable file in the loc range."""
        total = 0
        for path in resolve(self.walked, [self.range_spec()]):
            if (text := self._project.read(path)) is not None:
                total += len(text.splitlines())
        return total
