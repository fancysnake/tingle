"""Wiring contracts: the service surface gates are handed at construction."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Collection
    from pathlib import Path

    from tingle.pacts.check import CheckVerdict
    from tingle.pacts.config import CheckPolicy, Config, MetricDraft
    from tingle.pacts.diff import DiffReport
    from tingle.pacts.editor import EditorOpener
    from tingle.pacts.report import RunReport


class ConfigServiceProtocol(Protocol):
    """Discovering, validating, and editing tingle's configuration."""

    @abstractmethod
    def load(self, cwd: Path, override: Path | None = None) -> Config:
        """Discover, parse, and validate the configuration."""

    @abstractmethod
    def load_raw(self, cwd: Path) -> dict[str, Any]:
        """Raw config data for editing flows; empty when none exists yet."""

    @abstractmethod
    def add_metric(self, cwd: Path, draft: MetricDraft) -> tuple[Path, str]:
        """Append the drafted metric; return the file written and the name."""

    @abstractmethod
    def write_starter(self, cwd: Path) -> Path:
        """Create the starter config; raises FileExistsError if present."""


class MetricsServiceProtocol(Protocol):
    """Running the configured metrics, whole-tree or against a branch base."""

    @abstractmethod
    def run(self, config: Config, only: Collection[str] | None = None) -> RunReport:
        """Measure every selected metric over the whole project."""

    @abstractmethod
    def diff(
        self, config: Config, base: str, *, only: Collection[str] | None = None
    ) -> DiffReport:
        """Measure the branch's impact on every selected metric."""

    @abstractmethod
    def check(
        self,
        config: Config,
        base: str,
        *,
        only: Collection[str] | None = None,
        policy: CheckPolicy | None = None,
    ) -> tuple[DiffReport, CheckVerdict]:
        """Measure the branch, then judge it; `policy` overrides the config."""


class ServicesProtocol(Protocol):
    """The services a gate may reach; mirrors the inits registry."""

    @property
    @abstractmethod
    def config(self) -> ConfigServiceProtocol:
        """Configuration discovery and editing."""

    @property
    @abstractmethod
    def metrics(self) -> MetricsServiceProtocol:
        """Metric execution."""

    @property
    @abstractmethod
    def editor(self) -> EditorOpener:
        """Opening a located hit in the user's editor."""
