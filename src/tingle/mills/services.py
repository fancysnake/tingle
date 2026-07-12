"""Services: the orchestration a gate reaches for, one call per use case."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from tingle.mills.add import build_metric
from tingle.mills.config import validate
from tingle.mills.diff import DiffRunner
from tingle.mills.runner import run
from tingle.pacts.config import ConfigNotFoundError

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping
    from pathlib import Path

    from tingle.pacts.config import Config, ConfigStore, MetricDraft
    from tingle.pacts.diff import DiffReport, DiffSourceFactory
    from tingle.pacts.metrics import MetricType, ProjectFilesFactory
    from tingle.pacts.report import RunReport


@dataclass(frozen=True)
class ConfigService:
    """Discovering, validating, and editing tingle's configuration."""

    store: ConfigStore
    metric_types: Mapping[str, MetricType]

    def load(self, cwd: Path, override: Path | None = None) -> Config:
        """Discover, parse, and validate the configuration."""
        source, raw = self.store.load_raw(cwd, override)
        resolved = source.resolve()
        return validate(raw, self.metric_types, root=resolved.parent, source=resolved)

    def load_raw(self, cwd: Path) -> dict[str, Any]:
        """Raw config data for editing flows; empty when none exists yet."""
        try:
            return self.store.load_raw(cwd)[1]
        except ConfigNotFoundError:
            return {}

    def add_metric(self, cwd: Path, draft: MetricDraft) -> tuple[Path, str]:
        """Append the drafted metric; return the file written and the name.

        The draft is validated against the merged existing config before
        anything is written.
        """
        metric = build_metric(self.load_raw(cwd), self.metric_types, draft=draft)
        target = self.store.edit_target(cwd)
        self.store.append_metric(target, metric)
        return target, str(metric["name"])

    def write_starter(self, cwd: Path) -> Path:
        """Create the starter config; raises FileExistsError if present."""
        return self.store.write_starter(cwd)


@dataclass(frozen=True)
class MetricsService:
    """Running the configured metrics, whole-tree or against a branch base."""

    project_files: ProjectFilesFactory
    diff_source: DiffSourceFactory
    metric_types: Mapping[str, MetricType]

    def run(self, config: Config, only: Collection[str] | None = None) -> RunReport:
        """Measure every selected metric over the whole project."""
        return run(
            config,
            self.project_files(config.root),
            metric_types=self.metric_types,
            only=only,
        )

    def diff(
        self, config: Config, base: str, *, only: Collection[str] | None = None
    ) -> DiffReport:
        """Measure the branch's impact on every selected metric."""
        runner = DiffRunner(
            config=config,
            project=self.project_files(config.root),
            diff_source=self.diff_source(config.root),
            metric_types=self.metric_types,
        )
        return runner.run(base, only=only)
