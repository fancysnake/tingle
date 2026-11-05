"""Services: the orchestration a gate reaches for, one call per use case."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import PurePath
from typing import TYPE_CHECKING, Any

from tingle.mills.add import build_metric
from tingle.mills.check import judge
from tingle.mills.config import narrowed, validate
from tingle.mills.diff import DiffRunner
from tingle.mills.runner import run
from tingle.mills.starter import starter_bases
from tingle.mills.strict import judged_at_base, loosenings
from tingle.mills.templates import as_table, imported_paths, resolve, verify
from tingle.pacts.check import StrictVerdict
from tingle.pacts.config import (
    EVERY_METRIC,
    BaseConfig,
    ConfigError,
    ConfigNotFoundError,
    Library,
    LibraryEntry,
    Selection,
)
from tingle.pacts.metrics import uninterrupted, unwatched
from tingle.specs.ranges import UNREACHABLE_DIRS

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from pathlib import Path

    from tingle.pacts.check import CheckVerdict
    from tingle.pacts.config import (
        Config,
        ConfigStore,
        MetricDraft,
        MetricSpec,
        TemplateLoader,
    )
    from tingle.pacts.diff import BranchDiff, DiffReport, DiffSource, DiffSourceFactory
    from tingle.pacts.metrics import (
        Checkpoint,
        MetricType,
        ProgressSink,
        ProjectFiles,
        ProjectFilesFactory,
    )
    from tingle.pacts.report import RunReport
    from tingle.pacts.services import ConfigServiceProtocol


@dataclass(frozen=True)
class ConfigService:
    """Discovering, validating, and editing tingle's configuration."""

    store: ConfigStore
    metric_types: Mapping[str, MetricType]
    templates: TemplateLoader
    project_files: ProjectFilesFactory

    def load(self, cwd: Path, override: Path | None = None) -> Config:
        """Discover, parse, and validate the configuration."""
        source, raw = self.store.load_raw(cwd, override)
        resolved = source.resolve()
        errors: list[str] = []
        templates = self._templates(raw, errors)
        return validate(
            raw, self.metric_types, source=resolved, templates=templates, errors=errors
        )

    def at_base(
        self, config: Config, read: Callable[[PurePath], bytes | None]
    ) -> BaseConfig:
        """Return the configuration the branch started from, read through `read`.

        Its templates import from the tree as it stands: nothing else is
        installed. A base that no longer validates is not an error, because
        the branch cannot repair it; it only leaves nothing to compare with.
        """
        try:
            found = self.store.load_at(read, config.source.name)
        except ConfigError:
            return BaseConfig(problem="the base config cannot be parsed")
        if found is None:
            return BaseConfig(problem="the base has no config")
        name, raw = found
        asked = isinstance(table := raw.get("check"), Mapping) and (
            table.get("strict") is True
        )
        if not asked and not config.check.strict:
            return BaseConfig()
        errors: list[str] = []
        templates = self._templates(raw, errors)
        try:
            base = validate(
                raw,
                self.metric_types,
                source=config.root / name,
                templates=templates,
                errors=errors,
            )
        except ConfigError:
            return BaseConfig(problem="the base config does not validate", asked=asked)
        return BaseConfig(
            config=base, source=name, modules=self._modules(raw, config.root)
        )

    def differs_only_in_config(
        self, path: PurePath, *, before: bytes | None, after: bytes | None
    ) -> bool:
        """Whether a config file's two copies differ in tingle's config alone."""
        return self.store.differs_only_in_config(path, before=before, after=after)

    def _modules(self, raw: Mapping[str, Any], root: Path) -> tuple[PurePath, ...]:
        """List the project's own files among the modules of a config's templates.

        Only the module itself: what it imports in turn is not followed.
        """
        files = (self.templates.module_file(path) for path in imported_paths(raw))
        return tuple(
            PurePath(file.resolve().relative_to(root))
            for file in files
            if file is not None and file.resolve().is_relative_to(root)
        )

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
        templates = self._templates(
            raw, errors, extra_bases=() if draft.base is None else (draft.base,)
        )
        if errors:
            raise ConfigError(errors)
        metric = build_metric(raw, self.metric_types, draft=draft, templates=templates)
        target = self.store.edit_target(cwd)
        self.store.append_metric(target, metric)
        return target, str(metric["name"])

    def list_library(self, package: str) -> Library:
        """Every usable template a package offers, and why the rest are not.

        A pack is somebody else's code: one template that does not verify
        is worth saying out loud, but it is not a reason to answer "what
        is in this pack?" with nothing.
        """
        problems: list[str] = []
        entries: list[LibraryEntry] = []
        for path, obj in self.templates.catalogue(package).items():
            template = verify(
                obj, path=path, metric_types=self.metric_types, errors=problems
            )
            if template is None:
                continue
            table = as_table(template)
            entries.append(
                LibraryEntry(
                    path=path, table=table, toml=self.store.render_metric(table)
                )
            )
        return Library(entries=tuple(entries), problems=tuple(problems))

    def _templates(
        self,
        raw: Mapping[str, Any],
        errors: list[str],
        *,
        extra_bases: Iterable[str] = (),
    ) -> dict[str, Mapping[str, Any] | None]:
        return resolve(
            raw,
            self.templates,
            metric_types=self.metric_types,
            errors=errors,
            extra_bases=extra_bases,
        )

    def write_starter(self, cwd: Path) -> Path:
        """Create the starter config; raises ConfigError if present or unreadable.

        It starts on the templates of the tools the project configures,
        or on the generic examples when it configures none tingle knows.
        """
        if not (bases := starter_bases(self.project_files(cwd))):
            return self.store.write_examples(cwd)
        return self.store.write_starter(cwd, bases)

    def list_metric_types(self) -> tuple[MetricType, ...]:
        """Every metric type a config may name, in name order."""
        return tuple(sorted(self.metric_types.values(), key=lambda t: t.name))


@dataclass(frozen=True)
class MetricsService:
    """Running the configured metrics, whole-tree or against a branch base."""

    project_files: ProjectFilesFactory
    diff_source: DiffSourceFactory
    metric_types: Mapping[str, MetricType]
    configs: ConfigServiceProtocol

    def _files_of(self, config: Config) -> ProjectFiles:
        """Build the project tree, leaving what no range reaches unwalked.

        Deciding that stays here: the adapter is told which directories to
        skip rather than knowing any, so the exclusion and the skipping
        are the same list read twice.
        """
        return self.project_files(config.root, prune=UNREACHABLE_DIRS)

    def run(
        self,
        config: Config,
        selection: Selection = EVERY_METRIC,
        *,
        progress: ProgressSink = unwatched,
        checkpoint: Checkpoint = uninterrupted,
    ) -> RunReport:
        """Measure every selected metric over the whole project."""
        return run(
            narrowed(config, selection),
            self._files_of(config),
            metric_types=self.metric_types,
            progress=progress,
            checkpoint=checkpoint,
        )

    def diff(
        self,
        config: Config,
        base: str,
        *,
        selection: Selection = EVERY_METRIC,
        progress: ProgressSink = unwatched,
        checkpoint: Checkpoint = uninterrupted,
    ) -> DiffReport:
        """Measure the branch's impact on every selected metric."""
        runner = DiffRunner(
            config=narrowed(config, selection),
            project=self._files_of(config),
            diff_source=self.diff_source(config.root),
            metric_types=self.metric_types,
        )
        return runner.run(base, progress=progress, checkpoint=checkpoint)

    def check(self, config: Config, base: str) -> tuple[DiffReport, CheckVerdict]:
        """Measure the branch, then judge it on every metric the config names."""
        report = self.diff(config, base)
        verdict = judge(report, config.check)
        return report, replace(
            verdict, strict=self._strict(config, base=base, report=report)
        )

    def _strict(
        self, config: Config, *, base: str, report: DiffReport
    ) -> StrictVerdict:
        """Judge the branch's config against the one it started from."""
        source = self.diff_source(config.root)
        branch = source.branch_diff(base)
        at_base = self.configs.at_base(config, source.read_base)
        if at_base.config is None:
            asked = at_base.asked or config.check.strict
            return StrictVerdict(
                skipped=f"strict mode skipped: {at_base.problem}" if asked else None
            )
        if not at_base.config.check.strict:
            return StrictVerdict()
        judged = judged_at_base(at_base.config, self.metric_types)
        changed = {file.path for file in branch.files}
        modules = tuple(path for path in at_base.modules if path in changed)
        loosened = loosenings(
            at_base.config,
            config,
            judged=judged,
            scores=(self._scores(at_base.config, judged), _totals(report)),
            modules=modules,
        )
        if not loosened:
            return StrictVerdict()
        return StrictVerdict(
            loosened=loosened,
            alongside=self._alongside(
                config, source=source, branch=branch, at_base=at_base
            ),
        )

    def _scores(self, base: Config, judged: tuple[MetricSpec, ...]) -> dict[str, int]:
        """Measure the tree as it stands under the base's config."""
        if not judged:
            return {}
        names = tuple(spec.name for spec in judged)
        report = self.run(base, Selection(metrics=names))
        return {
            outcome.spec.name: outcome.stat.value
            for outcome in report.outcomes
            if outcome.stat is not None
        }

    def _alongside(
        self,
        config: Config,
        *,
        source: DiffSource,
        branch: BranchDiff,
        at_base: BaseConfig,
    ) -> tuple[PurePath, ...]:
        """Every file the branch changed that is not config."""
        project = self._files_of(config)
        files = {PurePath(config.source.name), at_base.source}
        return tuple(
            file.path
            for file in branch.files
            if file.path not in at_base.modules
            and not (
                file.path in files
                and self.configs.differs_only_in_config(
                    file.path,
                    before=source.read_base(file.path),
                    after=project.read(file.path),
                )
            )
        )


def _totals(report: DiffReport) -> dict[str, int]:
    return {
        outcome.spec.name: outcome.total.value
        for outcome in report.outcomes
        if outcome.total is not None
    }
