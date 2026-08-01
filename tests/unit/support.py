"""Fakes and builders shared by the unit tests.

Metric tests all begin the same way -- wrap a mapping of path to content
in a context, or a changed file in a diff context -- and the runner tests
all begin by wrapping a fake file tree in a Config. Those arrangements
live here once. Only the setup moves: every test still arranges, acts and
asserts in its own body.
"""

from __future__ import annotations

from pathlib import Path, PurePath
from typing import TYPE_CHECKING, Any

from tingle.pacts.config import Config, DisplaySpec, MetricSpec, RangeSpec
from tingle.pacts.diff import DiffMetricContext, FileDiff, FileStatus
from tingle.pacts.metrics import MetricContext

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


class FakeProject:
    """A project whose files are a mapping of path to content."""

    def __init__(self, contents: Mapping[str, str]) -> None:
        self._contents = dict(contents)

    def walk(self) -> Iterable[PurePath]:
        return sorted(PurePath(name) for name in self._contents)

    def read(self, path: PurePath) -> str | None:
        return self._contents.get(str(path))

    def exists(self, path: PurePath) -> bool:
        return str(path) in self._contents


PYTHON_RANGE = RangeSpec(name="python", include=("**/*.py",), default=True)

#: Two Python files and one that no Python range should match.
PROJECT = FakeProject({"a.py": "", "b.py": "", "notes.md": ""})


def make_config(
    *metrics: MetricSpec,
    display: DisplaySpec | None = None,
    extra_ranges: Mapping[str, RangeSpec] | None = None,
) -> Config:
    """Build a config measuring `metrics` over the default python range.

    `extra_ranges` names ranges beside the default one, for the tests
    that check a metric measured over something other than the default.
    """
    return Config(
        root=Path("/proj"),
        source=Path("/proj/tingle.toml"),
        ranges={"python": PYTHON_RANGE, **(extra_ranges or {})},
        metrics=metrics,
        default_range=PYTHON_RANGE,
        display=DisplaySpec() if display is None else display,
    )


def metric_context(
    contents: Mapping[str, str | None], params: Mapping[str, Any] | None = None
) -> MetricContext:
    """Measure over `contents`: every key is a file, `None` an unreadable one."""
    return MetricContext(
        files=tuple(PurePath(name) for name in contents),
        read=lambda path: contents.get(str(path)),
        exists=lambda path: str(path) in contents,
        params=params or {},
    )


def diff_context(
    current: Mapping[str, str | None],
    *,
    files: tuple[FileDiff, ...] = (),
    base: Mapping[str, str | None] | None = None,
    params: Mapping[str, Any] | None = None,
) -> DiffMetricContext:
    """Measure `files` against `current` content, with `base` as the old side."""
    was = base or {}
    return DiffMetricContext(
        files=files,
        read=lambda path: current.get(str(path)),
        read_base=lambda path: was.get(str(path)),
        params=params or {},
    )


def modified(
    path: str,
    *,
    added: frozenset[int] = frozenset(),
    removed: frozenset[int] = frozenset(),
) -> FileDiff:
    """Change `path`, touching the given line numbers on each side."""
    return FileDiff(
        path=PurePath(path),
        status=FileStatus.MODIFIED,
        added_lines=added,
        removed_lines=removed,
    )
