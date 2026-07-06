"""Contracts for diff-scoped metric runs (`tingle diff`)."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias

if TYPE_CHECKING:
    from pathlib import Path, PurePath

    from tingle.pacts.config import MetricSpec
    from tingle.pacts.metrics import MetricResult, Occurrence


class DiffSourceError(Exception):
    """The diff source (e.g. git) could not produce a branch diff."""


class FileStatus(StrEnum):
    """How the branch changed a file."""

    ADDED = "added"
    DELETED = "deleted"
    MODIFIED = "modified"


@dataclass(frozen=True)
class FileDiff:
    """One changed file: status plus touched line numbers on both sides.

    Line sets alone cannot distinguish created-empty, binary, or
    mode-only changes — that is what `status` is for. `removed_lines`
    are base-side line numbers.
    """

    path: PurePath
    status: FileStatus
    added_lines: frozenset[int] = frozenset()
    removed_lines: frozenset[int] = frozenset()


@dataclass(frozen=True)
class BranchDiff:
    """Everything the branch changed relative to the merge-base."""

    base_ref: str
    merge_base: str
    files: tuple[FileDiff, ...]


class DiffSource(Protocol):
    """Produces branch diffs and base-side file contents."""

    def branch_diff(self, base: str) -> BranchDiff:
        """Diff the working tree against merge-base(base, HEAD)."""
        ...

    def read_base(self, path: PurePath) -> str | None:
        """Return base-side file text, or None if missing/binary/undecodable."""
        ...


@dataclass(frozen=True)
class DiffMetricContext:
    """Everything a diff metric function may look at."""

    files: tuple[FileDiff, ...]
    read: Callable[[PurePath], str | None]
    read_base: Callable[[PurePath], str | None]
    params: Mapping[str, Any]


@dataclass(frozen=True)
class DiffResult:
    """Branch impact on one metric.

    Line-scoped metrics fill `added`/`removed` (net = added - removed);
    value-delta metrics report `net` only. Occurrences locate what the
    branch introduced and what it removed.
    """

    net: int
    added: int | None = None
    removed: int | None = None
    details: Mapping[str, int] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    added_occurrences: tuple[Occurrence, ...] = ()
    removed_occurrences: tuple[Occurrence, ...] = ()


DiffMetricFunction: TypeAlias = Callable[[DiffMetricContext], DiffResult]


@dataclass(frozen=True)
class DiffOutcome:
    """Diff result of one metric plus the current full-repo total."""

    spec: MetricSpec
    range_names: tuple[str, ...]
    result: DiffResult | None = None
    total: MetricResult | None = None
    error: str | None = None


@dataclass(frozen=True)
class DiffReport:
    """The outcome of one `tingle diff` run.

    `skipped` names metrics whose type has no diff variant.
    """

    root: Path
    source: Path
    base_ref: str
    merge_base: str
    outcomes: tuple[DiffOutcome, ...]
    skipped: tuple[str, ...] = ()
