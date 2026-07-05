"""Contracts for tingle's own configuration."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ConfigNotFoundError(Exception):
    """No tingle.toml file or [tool.tingle] section could be found."""


class ConfigError(Exception):
    """The configuration is invalid; carries every problem found."""

    def __init__(self, errors: list[str]) -> None:
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


@dataclass(frozen=True)
class Config:
    """Validated tingle configuration."""

    root: Path
    source: Path
    ranges: Mapping[str, RangeSpec]
    metrics: tuple[MetricSpec, ...]
    default_range: RangeSpec
