"""Contracts for tingle's own configuration."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


#: Stand-in guide for an outcome built without one. The real fallback, when
#: neither a metric nor [display] pins a guide, is derived from the size of
#: the codebase -- which only a run can know, so it cannot be a default here.
DEFAULT_GUIDE = 100


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
class DisplaySpec:
    """The `[display]` settings: how measured values are presented.

    `guide` is the value a metric is judged against — the point at which
    its debt is considered to have reached full size. Left unset, it is
    derived from the size of the codebase, so debt is read as a density
    rather than an absolute count. Setting it pins one guide for every
    metric that does not name its own, whatever the codebase does.

    `loc_range` names the range those lines are counted over; unset, the
    default range stands for "the project".
    """

    guide: int | None = None
    loc_range: str | None = None


@dataclass(frozen=True)
class MetricSpec:
    """One configured metric. Empty `ranges` means the default range applies.

    A `guide` of None inherits the one from `[display]`; the runner
    resolves that fallback, so nothing downstream repeats it.
    """

    name: str
    type: str
    ranges: tuple[str, ...] = ()
    params: Mapping[str, Any] = field(default_factory=dict)
    group: str | None = None
    guide: int | None = None
    description: str | None = None


class CheckPolicy(StrEnum):
    """When `tingle check` calls a branch a regression.

    SUM weighs the branch as a whole: debt paid off in one metric offsets
    debt taken on in another. ANY forbids the trade — no single metric may
    grow, whatever else improved.
    """

    SUM = "sum"
    ANY = "any"


@dataclass(frozen=True)
class CheckSpec:
    """The `[check]` settings: how to judge a branch, and what to overlook.

    `ignore` names metrics that neither fail the check nor appear in its
    output — the ones expected to grow, like lines of code.
    """

    policy: CheckPolicy = CheckPolicy.SUM
    ignore: tuple[str, ...] = ()


@dataclass(frozen=True)
class Config:
    """Validated tingle configuration."""

    root: Path
    source: Path
    ranges: Mapping[str, RangeSpec]
    metrics: tuple[MetricSpec, ...]
    default_range: RangeSpec
    diff_base: str | None = None
    check: CheckSpec = field(default_factory=CheckSpec)
    display: DisplaySpec = field(default_factory=DisplaySpec)


@dataclass(frozen=True)
class MetricDraft:
    """User input for `tingle add`, before validation."""

    type_name: str
    value: str | None = None
    name: str | None = None
    ranges: tuple[str, ...] = ()
    params: Mapping[str, str] = field(default_factory=dict)
    group: str | None = None
    description: str | None = None


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
