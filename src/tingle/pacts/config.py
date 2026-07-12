"""Contracts for tingle's own configuration."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


class ConfigNotFoundError(Exception):
    """No tingle.toml file or [tool.tingle] section could be found."""


class ConfigError(Exception):
    """The configuration is invalid; carries every problem found."""

    def __init__(self, errors: list[str]) -> None:
        """Collect every problem found; the message joins them."""
        self.errors = errors
        super().__init__("\n".join(errors))


@dataclass(frozen=True)
class RangeSpec:
    """A named file set defined by include/exclude glob patterns."""

    name: str
    include: tuple[str, ...]
    exclude: tuple[str, ...] = ()
    default: bool = False


@dataclass(frozen=True)
class MetricSpec:
    """One configured metric. Empty `ranges` means the default range applies."""

    name: str
    type: str
    ranges: tuple[str, ...] = ()
    params: Mapping[str, Any] = field(default_factory=dict)
    group: str | None = None


@dataclass(frozen=True)
class Config:
    """Validated tingle configuration."""

    root: Path
    source: Path
    ranges: Mapping[str, RangeSpec]
    metrics: tuple[MetricSpec, ...]
    default_range: RangeSpec
    diff_base: str | None = None


@dataclass(frozen=True)
class MetricDraft:
    """User input for `tingle add`, before validation."""

    type_name: str
    value: str | None = None
    name: str | None = None
    ranges: tuple[str, ...] = ()
    params: Mapping[str, str] = field(default_factory=dict)
    group: str | None = None


class ConfigStore(Protocol):
    """Reads and edits the file tingle's own configuration lives in."""

    @abstractmethod
    def load_raw(
        self, root: Path, override: Path | None = None
    ) -> tuple[Path, dict[str, Any]]:
        """Locate and parse the configuration; raises ConfigNotFoundError."""

    @abstractmethod
    def edit_target(self, root: Path) -> Path:
        """Return the file `tingle add` should write to, existing or not."""

    @abstractmethod
    def append_metric(self, path: Path, metric: Mapping[str, Any]) -> None:
        """Append a metric entry, preserving existing formatting."""

    @abstractmethod
    def write_starter(self, root: Path) -> Path:
        """Create the starter config; raises FileExistsError if present."""
