"""Invariants of range resolution."""

from __future__ import annotations

from tingle.pacts.metrics import UnreachableDir

#: The directories a range never reaches, whatever a config asks for.
#:
#: Stated once, in the shape that carries both readings of it: the glob
#: every range excludes, and the name the tree walk declines to descend
#: into. A second list would be the same fact written twice, and the day
#: the two disagreed a run would report on files it had refused to read.
#:
#: Anchored means "only as a child of the project root". Most of these are:
#: a `.venv` beside `src/` is the project's own, while one nested inside a
#: package is a file like any other and is measured. `__pycache__` is the
#: exception -- it is generated wherever Python runs, so it is unreachable
#: at every depth.
UNREACHABLE_DIRS = (
    UnreachableDir(".git", anchored=True),
    UnreachableDir(".venv", anchored=True),
    UnreachableDir("__pycache__", anchored=False),
    UnreachableDir("node_modules", anchored=True),
    UnreachableDir("dist", anchored=True),
    UnreachableDir(".tox", anchored=True),
    UnreachableDir(".mise", anchored=True),
)

#: What range matching appends to every spec's own excludes.
DEFAULT_EXCLUDES = tuple(directory.glob for directory in UNREACHABLE_DIRS)
