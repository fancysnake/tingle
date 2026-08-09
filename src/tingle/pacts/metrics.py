"""Contracts between the metric runner and metric functions."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
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
    def __call__(self, root: Path) -> ProjectFiles:
        """Return a ProjectFiles rooted at `root`."""


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
    """A measured value with optional per-item details and warnings."""

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
