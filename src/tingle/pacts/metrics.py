"""Contracts between the metric runner and metric functions."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias

if TYPE_CHECKING:
    from pathlib import Path, PurePath

    from tingle.pacts.diff import DiffMetricFunction

#: Bytes sniffed for a NUL before a file is called binary, which is the
#: window git's own differ uses. Two layers apply it -- mills to decide
#: what a metric may read, the git adapter to decide what git would have
#: diffed -- so it is a fact about the bytes crossing `read()` rather than
#: either layer's own rule.
BINARY_SNIFF_BYTES = 8000


def sniffed_binary(data: bytes) -> bool:
    """Report whether git would call these bytes binary.

    The window and the test are one fact, so they are stated together and
    read the same on both sides of `read()`.
    """
    return b"\0" in data[:BINARY_SNIFF_BYTES]


class RunPhase(StrEnum):
    """Which part of a run is under way.

    Named after what the run is doing rather than how long it has left,
    because the three do not measure in the same unit: two of them are
    bounded by a number known before they start and one is not.
    """

    SCANNING = "scanning"
    DIFFING = "diffing"
    MEASURING = "measuring"


@dataclass(frozen=True)
class RunProgress:
    """How far a run has got, as the runner last knew it.

    `total` is None while the work is unbounded -- walking a tree cannot
    say how big it is until it has finished walking it -- so a view shows
    those two states differently rather than inventing a denominator.

    `done` counts what is finished, so it never reaches `total` while
    anything is still running: a run reports that it is starting the
    metric it names, not that it has just finished one.
    """

    phase: RunPhase
    done: int = 0
    total: int | None = None
    label: str = ""


#: Told how far a run has got, whenever the run knows.
#:
#: Must be cheap and must not raise. A run does not guard against a sink
#: that does: the isolation around a metric is there to keep one bad
#: metric from ending the run, and catching a broken sink inside it would
#: report the metric as failed because the progress bar did.
ProgressSink: TypeAlias = Callable[[RunProgress], None]


def unwatched(_: RunProgress) -> None:
    """Take the progress of a run nobody is watching, and drop it.

    The default sink, so that a run reports the same way whether or not
    anyone is listening. No caller distinguishes "no sink" from a sink
    that drops it, and making that the default is what lets every runner
    say `note(...)` outright rather than guarding each report.
    """


@dataclass(frozen=True)
class UnreachableDir:
    """A directory whose contents no range can ever match.

    Three layers hold a piece of this: `specs` names which directories
    they are, `mills` excludes them from every range, and the tree adapter
    declines to descend into them at all. That makes it a contract rather
    than either layer's own rule -- the exclusion and the skipping have to
    mean the same thing, or a run would measure what it says it does not.

    `anchored` is the difference between a directory that is unreachable
    only as a child of the project root and one that is unreachable
    wherever it appears. It is not decoration: a `.venv` nested inside a
    package is measured, and skipping it would quietly change what a run
    reports.
    """

    name: str
    anchored: bool

    @property
    def glob(self) -> str:
        """The exclude pattern that says the same thing to range matching."""
        return f"{self.name}/**" if self.anchored else f"**/{self.name}/**"


class ProjectFiles(Protocol):
    """Read-only view of the project tree."""

    @abstractmethod
    def walk(self) -> Iterable[PurePath]:
        """Yield every file under the project root as a relative path."""

    @abstractmethod
    def read(self, path: PurePath) -> bytes | None:
        """Return the file's raw bytes, or None if it cannot be read.

        Adapters do not decode: whether bytes are text is a measurement
        rule, and it is applied in one place upstream of every metric.
        """

    @abstractmethod
    def exists(self, path: PurePath) -> bool:
        """Return whether the file exists."""


class ProjectFilesFactory(Protocol):
    """Builds the project-tree view anchored at a root directory."""

    @abstractmethod
    def __call__(
        self, root: Path, *, prune: Sequence[UnreachableDir] = ()
    ) -> ProjectFiles:
        """Return a ProjectFiles rooted at `root`, skipping `prune`.

        Pruning is an optimisation and never a filter: only directories
        nothing could match belong in it, so a view built without one
        measures the same files, slower.
        """


@dataclass(frozen=True)
class MetricContext:
    """Everything a metric function may look at."""

    files: tuple[PurePath, ...]
    read: Callable[[PurePath], str | None]
    exists: Callable[[PurePath], bool]
    params: Mapping[str, Any]


@dataclass(frozen=True)
class Occurrence:
    """One located hit: a file plus optional line, or a list-entry note."""

    path: str
    line: int | None = None
    note: str | None = None

    def __str__(self) -> str:
        """Render as path:line, path: note, or bare path."""
        if self.line is not None:
            return f"{self.path}:{self.line}"
        if self.note is not None:
            return f"{self.path}: {self.note}"
        return self.path


@dataclass(frozen=True)
class MetricResult:
    """A measured value with optional per-item details and warnings.

    `details` is per-item weight, not a decomposition of `value`: it says
    how heavily each item is involved, and only a metric whose value is the
    total weight has them sum to it. A spread metric counts each file once
    however many hits it holds, so its details can sum to more than its
    value.
    """

    value: int
    details: Mapping[str, int] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    occurrences: tuple[Occurrence, ...] = ()


MetricFunction: TypeAlias = Callable[[MetricContext], MetricResult]


@dataclass(frozen=True)
class ParamSchema:
    """A metric type's parameter contract: what `add` and validation read."""

    required: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()
    primary: str | None = None
    validate: Callable[[Mapping[str, Any]], list[str]] | None = None


@dataclass(frozen=True)
class MetricType:
    """A metric type: dispatch target plus the data driving add/list/validation."""

    name: str
    func: MetricFunction
    params: ParamSchema = field(default_factory=ParamSchema)
    description: str = ""
    diff_func: DiffMetricFunction | None = None
