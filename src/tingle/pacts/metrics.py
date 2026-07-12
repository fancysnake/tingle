"""Contracts between the metric runner and metric functions."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias

if TYPE_CHECKING:
    from pathlib import Path, PurePath

    from tingle.pacts.diff import DiffMetricFunction


class ProjectFiles(Protocol):
    """Read-only view of the project tree."""

    @abstractmethod
    def walk(self) -> Iterable[PurePath]:
        """Yield every file under the project root as a relative path."""

    @abstractmethod
    def read(self, path: PurePath) -> str | None:
        """Return file text, or None if missing, binary, or undecodable."""

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

    @property
    def sort_key(self) -> tuple[str, int, str]:
        """Deterministic ordering: by path, then line, then note."""
        return (self.path, self.line or 0, self.note or "")

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
