"""Contracts between the metric runner and metric functions."""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from pathlib import PurePath


class ProjectFiles(Protocol):
    """Read-only view of the project tree."""

    def walk(self) -> Iterable[PurePath]:
        """Yield every file under the project root as a relative path."""
        ...

    def read(self, path: PurePath) -> str | None:
        """Return file text, or None if missing, binary, or undecodable."""
        ...

    def exists(self, path: PurePath) -> bool:
        """Return whether the file exists."""
        ...


@dataclass(frozen=True)
class MetricContext:
    """Everything a metric function may look at."""

    files: tuple[PurePath, ...]
    read: Callable[[PurePath], str | None]
    exists: Callable[[PurePath], bool]
    params: Mapping[str, Any]


@dataclass(frozen=True)
class MetricResult:
    """A measured value with optional per-item details and warnings."""

    value: int
    details: Mapping[str, int] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


type MetricFunction = Callable[[MetricContext], MetricResult]


@dataclass(frozen=True)
class MetricType:
    """A metric type: dispatch target plus the data driving add/list/validation."""

    name: str
    func: MetricFunction
    required_params: tuple[str, ...] = ()
    optional_params: tuple[str, ...] = ()
    primary_param: str | None = None
    validate_params: Callable[[Mapping[str, Any]], list[str]] | None = None
    description: str = ""
