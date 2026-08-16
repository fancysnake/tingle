"""Services: the orchestration a gate reaches for, one call per use case."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from tingle.mills.add import build_metric
from tingle.mills.check import judge
from tingle.mills.config import validate
from tingle.mills.diff import DiffRunner
from tingle.mills.runner import run
from tingle.mills.templates import resolve, verify
from tingle.pacts.config import ConfigError, ConfigNotFoundError, LibraryEntry

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping
    from pathlib import Path

    from tingle.pacts.check import CheckVerdict
    from tingle.pacts.config import (
        CheckPolicy,
        Config,
        ConfigStore,
        MetricDraft,
        MetricTemplate,
        TemplateLoader,
    )
    from tingle.pacts.diff import DiffReport, DiffSourceFactory
    from tingle.pacts.metrics import MetricType, ProjectFilesFactory
    from tingle.pacts.report import RunReport


@dataclass(frozen=True)
class ConfigService:
    """Discovering, validating, and editing tingle's configuration."""

    store: ConfigStore
    metric_types: Mapping[str, MetricType]
    templates: TemplateLoader

    def load(self, cwd: Path, override: Path | None = None) -> Config:
        """Discover, parse, and validate the configuration."""
        source, raw = self.store.load_raw(cwd, override)
        resolved = source.resolve()
        errors: list[str] = []
        templates = self._templates(raw, errors)
        try:
            config = validate(
                raw,
                self.metric_types,
                root=resolved.parent,
                source=resolved,
                templates=templates,
            )
        except ConfigError as exc:
            # one pass over the whole file: a broken template and a broken
            # metric are both problems the reader has, and reporting them a
            # round apart makes a fix take two runs.
            raise ConfigError([*errors, *exc.errors]) from None
        if errors:
            raise ConfigError(errors)
        return config

    def load_raw(self, cwd: Path) -> dict[str, Any]:
        """Raw config data for editing flows; empty when none exists yet."""
        try:
            return self.store.load_raw(cwd)[1]
        except ConfigNotFoundError:
            return {}

    def add_metric(self, cwd: Path, draft: MetricDraft) -> tuple[Path, str]:
        """Append the drafted metric; return the file written and the name.

        The draft is validated against the merged existing config before
        anything is written, base and all -- so a template that does not
        exist is caught here rather than on the next run.
        """
        raw = self.load_raw(cwd)
        errors: list[str] = []
        existing = raw.get("metrics", [])
        drafted = (
            [*existing, {"base": draft.base}] if isinstance(existing, list) else []
        )
        templates = self._templates({**raw, "metrics": drafted}, errors)
        if errors:
            raise ConfigError(errors)
        metric = build_metric(raw, self.metric_types, draft=draft, templates=templates)
        target = self.store.edit_target(cwd)
        self.store.append_metric(target, metric)
        return target, str(metric["name"])

    def list_library(self, package: str) -> tuple[LibraryEntry, ...]:
        """Every usable template a package offers, in path order."""
        errors: list[str] = []
        entries = tuple(
            LibraryEntry(path=path, template=template)
            for path, obj in self.templates.catalogue(package).items()
            if (
                template := verify(
                    obj, path=path, metric_types=self.metric_types, errors=errors
                )
            )
            is not None
        )
        if errors:
            raise ConfigError(errors)
        return entries

    def _templates(
        self, raw: Mapping[str, Any], errors: list[str]
    ) -> dict[str, MetricTemplate]:
        return resolve(
            raw, self.templates, metric_types=self.metric_types, errors=errors
        )

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

    def check(
        self,
        config: Config,
        base: str,
        *,
        only: Collection[str] | None = None,
        policy: CheckPolicy | None = None,
    ) -> tuple[DiffReport, CheckVerdict]:
        """Measure the branch, then judge it; `policy` overrides the config."""
        report = self.diff(config, base, only=only)
        spec = config.check if policy is None else replace(config.check, policy=policy)
        return report, judge(report, spec)
