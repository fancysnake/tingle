"""Services: the orchestration a gate reaches for, one call per use case."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from tingle.mills.add import build_metric
from tingle.mills.check import judge
from tingle.mills.config import asks_for_strict, narrowed, validate
from tingle.mills.diff import DiffRunner
from tingle.mills.runner import project_tree, run
from tingle.mills.starter import starter_bases
from tingle.mills.templates import as_table, imported_paths, resolve, verify
from tingle.pacts.config import (
    EVERY_METRIC,
    BaseConfig,
    BaseConfigError,
    ConfigError,
    ConfigNotFoundError,
    Library,
    LibraryEntry,
)
from tingle.pacts.metrics import uninterrupted, unwatched

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping
    from pathlib import Path, PurePath

    from tingle.pacts.check import CheckVerdict
    from tingle.pacts.config import (
        Config,
        ConfigStore,
        MetricDraft,
        Selection,
        TemplateLoader,
    )
    from tingle.pacts.diff import DiffReport, DiffSource, DiffSourceFactory
    from tingle.pacts.metrics import (
        Checkpoint,
        MetricType,
        ProgressSink,
        ProjectFilesFactory,
    )
    from tingle.pacts.report import RunReport
    from tingle.pacts.services import StrictServiceProtocol


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
    ) -> BaseConfig | None:
        """Return the strict config the branch started from, read through `read`.

        None when the base asked for no strict. Its templates import from the
        tree as it stands: nothing else is installed. A base that no longer
        validates raises BaseConfigError for the caller to report, because
        the branch cannot repair it.
        """
        try:
            found = self.store.load_at(read, config.source.name)
        except ConfigError as exc:
            msg = "the base config cannot be parsed"
            raise BaseConfigError(msg) from exc
        if found is None:
            if config.check.strict:
                msg = "the base has no config"
                raise BaseConfigError(msg)
            return None
        name, raw = found
        asked = asks_for_strict(raw)
        if not asked and not config.check.strict:
            return None
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
        except ConfigError as exc:
            msg = "the base config does not validate"
            bases = tuple(imported_paths(raw)) if asked else ()
            raise BaseConfigError(msg, source=name, bases=bases) from exc
        if not asked:
            return None
        return BaseConfig(
            config=base, source=name, modules=self._modules(raw, config.root)
        )

    def _modules(self, raw: Mapping[str, Any], root: Path) -> tuple[PurePath, ...]:
        """List the project's own files among the modules of a config's templates.

        Only the module itself: what it imports in turn is not followed.
        """
        files = (self.templates.module_file(path, root) for path in imported_paths(raw))
        return tuple(file for file in files if file is not None)

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
    strict: StrictServiceProtocol

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
            project_tree(self.project_files, config),
            metric_types=self.metric_types,
            progress=progress,
            checkpoint=checkpoint,
        )

    def diff(
        self,
        config: Config,
        base: str | None,
        *,
        selection: Selection = EVERY_METRIC,
        progress: ProgressSink = unwatched,
        checkpoint: Checkpoint = uninterrupted,
    ) -> DiffReport:
        """Measure the branch's impact on every selected metric."""
        runner = self._runner(
            narrowed(config, selection), self.diff_source(config.root)
        )
        return runner.run(
            _base_of(config, base), progress=progress, checkpoint=checkpoint
        )

    def _runner(self, config: Config, source: DiffSource) -> DiffRunner:
        return DiffRunner(
            config=config,
            project=project_tree(self.project_files, config),
            diff_source=source,
            metric_types=self.metric_types,
        )

    def check(
        self, config: Config, base: str | None
    ) -> tuple[DiffReport, CheckVerdict]:
        """Measure the branch, then judge it on every metric the config names.

        One source serves both, because it reads the base only once it has
        diffed.
        """
        source = self.diff_source(config.root)
        report = self._runner(config, source).run(_base_of(config, base))
        verdict = judge(report, config.check)
        return report, replace(
            verdict, strict=self.strict.judge(config, source=source, report=report)
        )


def _base_of(config: Config, base: str | None) -> str:
    return base or config.diff_base
