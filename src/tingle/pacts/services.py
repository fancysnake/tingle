"""Wiring contracts: the service surface gates are handed at construction."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Protocol

from tingle.pacts.config import EVERY_METRIC, Selection

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from tingle.pacts.browse import BrowseState, Row, SortKey
    from tingle.pacts.check import CheckVerdict
    from tingle.pacts.config import CheckPolicy, Config, Library, MetricDraft
    from tingle.pacts.diff import DiffOutcome, DiffReport
    from tingle.pacts.editor import EditorOpener
    from tingle.pacts.metrics import MetricType
    from tingle.pacts.report import MetricOutcome, ReportSection, RunReport


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

    @abstractmethod
    def list_metric_types(self) -> tuple[MetricType, ...]:
        """Every metric type a config may name, in name order."""

    @abstractmethod
    def list_library(self, package: str) -> Library:
        """Every usable template a package offers, and why the rest are not."""


class MetricsServiceProtocol(Protocol):
    """Running the configured metrics, whole-tree or against a branch base."""

    @abstractmethod
    def run(self, config: Config, selection: Selection = EVERY_METRIC) -> RunReport:
        """Measure every selected metric over the whole project."""

    @abstractmethod
    def diff(
        self, config: Config, base: str, *, selection: Selection = EVERY_METRIC
    ) -> DiffReport:
        """Measure the branch's impact on every selected metric."""

    @abstractmethod
    def check(
        self,
        config: Config,
        base: str,
        *,
        selection: Selection = EVERY_METRIC,
        policy: CheckPolicy | None = None,
    ) -> tuple[DiffReport, CheckVerdict]:
        """Measure the branch, then judge it; `policy` overrides the config."""


class BrowseServiceProtocol(Protocol):
    """Driving a browsing session: what is visible, folded, sorted, searched.

    Every call is pure -- a `BrowseState` goes in and a new one, or the
    rows it should be drawn as, comes out. The gate holds the state and
    the widgets; which rows that state means is decided here.
    """

    @abstractmethod
    def start(
        self, sections: Sequence[ReportSection[MetricOutcome | DiffOutcome]]
    ) -> BrowseState:
        """Open a session over the sections of a finished report."""

    @abstractmethod
    def rows(self, state: BrowseState) -> tuple[Row, ...]:
        """Every row that should be drawn, in the order it should be drawn."""

    @abstractmethod
    def outlined(self, state: BrowseState) -> bool:
        """Whether the rows still nest under group headers."""

    @abstractmethod
    def push_sort(
        self, state: BrowseState, key: SortKey, *, descending: bool = False
    ) -> BrowseState:
        """Sort by `key`, keeping the previous sorts as tie-breakers."""

    @abstractmethod
    def clear_sort(self, state: BrowseState) -> BrowseState:
        """Drop every sort, returning the rows to config order."""

    @abstractmethod
    def set_query(self, state: BrowseState, query: str) -> BrowseState:
        """Search for `query`, or leave search mode when it is empty."""

    @abstractmethod
    def set_fold(self, state: BrowseState, key: str, *, folded: bool) -> BrowseState:
        """Fold or unfold one row."""

    @abstractmethod
    def toggle_fold_all(self, state: BrowseState) -> BrowseState:
        """Fold every group at once, or unfold them all once none is folded."""

    @abstractmethod
    def fold_quiet_groups(self, state: BrowseState) -> BrowseState:
        """Fold away the groups the report has nothing to say about."""


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
    def browse(self) -> BrowseServiceProtocol:
        """What an interactive session shows, and in what order."""

    @property
    @abstractmethod
    def editor(self) -> EditorOpener:
        """Opening a located hit in the user's editor."""
