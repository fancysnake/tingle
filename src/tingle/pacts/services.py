"""Wiring contracts: the service surface gates are handed at construction."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Collection
    from pathlib import Path

    from tingle.pacts.config import Config, MetricDraft
    from tingle.pacts.diff import DiffReport
    from tingle.pacts.report import RunReport


class ConfigServiceProtocol(Protocol):
    """Discovering, validating, and editing tingle's configuration."""

    def load(self, cwd: Path, override: Path | None = None) -> Config:
        """Discover, parse, and validate the configuration."""
        ...

    def load_raw(self, cwd: Path) -> dict[str, Any]:
        """Raw config data for editing flows; empty when none exists yet."""
        ...

    def add_metric(self, cwd: Path, draft: MetricDraft) -> tuple[Path, str]:
        """Append the drafted metric; return the file written and the name."""
        ...

    def write_starter(self, cwd: Path) -> Path:
        """Create the starter config; raises FileExistsError if present."""
        ...


class MetricsServiceProtocol(Protocol):
    """Running the configured metrics, whole-tree or against a branch base."""

    def run(self, config: Config, only: Collection[str] | None = None) -> RunReport:
        """Measure every selected metric over the whole project."""
        ...

    def diff(
        self, config: Config, base: str, only: Collection[str] | None = None
    ) -> DiffReport:
        """Measure the branch's impact on every selected metric."""
        ...


class ServicesProtocol(Protocol):
    """The services a gate may reach; mirrors the inits registry."""

    @property
    def config(self) -> ConfigServiceProtocol:
        """Configuration discovery and editing."""
        ...

    @property
    def metrics(self) -> MetricsServiceProtocol:
        """Metric execution."""
        ...
