"""Services: the orchestration a gate reaches for, one call per use case."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from tingle.mills.add import build_metric
from tingle.mills.check import judge
from tingle.mills.config import narrowed, validate
from tingle.mills.diff import DiffRunner
from tingle.mills.runner import run
from tingle.pacts.config import EVERY_METRIC, ConfigNotFoundError, Selection
from tingle.specs.ranges import UNREACHABLE_DIRS

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from tingle.pacts.check import CheckVerdict
    from tingle.pacts.config import CheckPolicy, Config, ConfigStore, MetricDraft
    from tingle.pacts.diff import DiffReport, DiffSourceFactory
    from tingle.pacts.metrics import MetricType, ProjectFiles, ProjectFilesFactory
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

    def list_metric_types(self) -> tuple[MetricType, ...]:
        """Every metric type a config may name, in name order."""
        return tuple(sorted(self.metric_types.values(), key=lambda t: t.name))


@dataclass(frozen=True)
class MetricsService:
    """Running the configured metrics, whole-tree or against a branch base."""

    project_files: ProjectFilesFactory
    diff_source: DiffSourceFactory
    metric_types: Mapping[str, MetricType]

    def _files_of(self, config: Config) -> ProjectFiles:
        """Build the project tree, leaving what no range reaches unwalked.

        Deciding that stays here: the adapter is told which directories to
        skip rather than knowing any, so the exclusion and the skipping
        are the same list read twice.
        """
        return self.project_files(config.root, prune=UNREACHABLE_DIRS)

    def run(self, config: Config, selection: Selection = EVERY_METRIC) -> RunReport:
        """Measure every selected metric over the whole project."""
        return run(
            narrowed(config, selection),
            self._files_of(config),
            metric_types=self.metric_types,
        )

    def diff(
        self, config: Config, base: str, *, selection: Selection = EVERY_METRIC
    ) -> DiffReport:
        """Measure the branch's impact on every selected metric."""
        runner = DiffRunner(
            config=narrowed(config, selection),
            project=self._files_of(config),
            diff_source=self.diff_source(config.root),
            metric_types=self.metric_types,
        )
        return runner.run(base)

    def check(
        self,
        config: Config,
        base: str,
        *,
        selection: Selection = EVERY_METRIC,
        policy: CheckPolicy | None = None,
    ) -> tuple[DiffReport, CheckVerdict]:
        """Measure the branch, then judge it; `policy` overrides the config."""
        report = self.diff(config, base, selection=selection)
        spec = config.check if policy is None else replace(config.check, policy=policy)
        return report, judge(report, spec)
