"""Comparing a branch's config with the one its base holds."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePath
from typing import TYPE_CHECKING

from tingle.mills.config import narrowed
from tingle.mills.runner import project_tree, run
from tingle.pacts.check import Loosening, StrictVerdict
from tingle.pacts.config import BaseConfigError, CheckPolicy, Selection

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

    from tingle.pacts.config import Config, ConfigStore, MetricSpec
    from tingle.pacts.diff import DiffReport
    from tingle.pacts.metrics import MetricType, ProjectFilesFactory
    from tingle.pacts.report import RunReport
    from tingle.pacts.services import ConfigServiceProtocol


@dataclass(frozen=True)
class Scores:
    """The branch's tree measured under the base's config, then under its own."""

    before: Mapping[str, int]
    after: Mapping[str, int]


def judged_at_base(
    base: Config, metric_types: Mapping[str, MetricType]
) -> tuple[MetricSpec, ...]:
    """Select the metrics the base's check takes account of.

    A metric the base ignores, or one with no diff variant, never decided
    a check, so changing it weakens nothing.
    """
    return tuple(
        spec
        for spec in base.metrics
        if spec.name not in base.check.ignore
        and metric_types[spec.type].diff_func is not None
    )


def loosenings(
    base: Config,
    own: Config,
    *,
    judged: tuple[MetricSpec, ...],
    scores: Scores,
    modules: tuple[PurePath, ...] = (),
) -> tuple[Loosening, ...]:
    """Every way `own` weakens the gate `base` set up.

    `scores` measures one tree under both configs, so only the config can
    have moved a number. A metric that answered under one and not the other
    is not compared. `modules` are
    the template modules the branch changed: nothing older than the
    installed tree can be imported to measure them against, so a change is
    all that can be said of one.
    """
    found: list[Loosening] = []
    if base.check.strict and not own.check.strict:
        found.append(Loosening("[check] strict", "turned off"))
    if base.check.policy is CheckPolicy.ANY and own.check.policy is CheckPolicy.SUM:
        found.append(Loosening("[check] policy", "any to sum"))
    names = {spec.name for spec in own.metrics}
    before, after = scores.before, scores.after
    for spec in judged:
        name = spec.name
        if name not in names:
            found.append(Loosening(name, "removed"))
        elif name in own.check.ignore:
            found.append(Loosening(name, "moved to [check] ignore"))
        elif name in before and name in after and after[name] < before[name]:
            found.append(Loosening(name, f"{before[name]} to {after[name]}"))
    return (*found, *module_loosenings(modules))


def module_loosenings(modules: Iterable[PurePath]) -> tuple[Loosening, ...]:
    """Report each template module the branch changed."""
    return tuple(Loosening(str(path), "template module changed") for path in modules)


def changed_modules(
    bases: Iterable[str], changed: Iterable[PurePath]
) -> tuple[PurePath, ...]:
    """Pick the changed files that dotted template `bases` run through.

    The files are told from the paths alone, because a deleted module no
    longer imports to say where it was.
    """
    dotted = [tuple(base.split(".")[:-1]) for base in bases]
    return tuple(
        path
        for path in changed
        if path.suffix == ".py" and any(_reaches(mods, path) for mods in dotted)
    )


def _reaches(modules: tuple[str, ...], path: PurePath) -> bool:
    """Whether `path` ends in the file of a module along dotted `modules`.

    Only the tail is compared, so `src/pack/rules.py` is `pack.rules`
    wherever the package root sits.
    """
    # shortcut: a package mapped onto a directory of another name is missed,
    # ask the template loader first if one turns up
    parts = path.with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return any(
        parts[-depth:] == modules[:depth] for depth in range(1, len(modules) + 1)
    )


@dataclass(frozen=True)
class StrictService:
    """Judging a branch's config against the one it started from."""

    configs: ConfigServiceProtocol
    store: ConfigStore
    project_files: ProjectFilesFactory
    metric_types: Mapping[str, MetricType]

    def judge(
        self,
        config: Config,
        *,
        read_base: Callable[[PurePath], bytes | None],
        report: DiffReport,
    ) -> StrictVerdict:
        """Judge the branch's config against the one it started from."""
        try:
            at_base = self.configs.at_base(config, read_base)
        except BaseConfigError as exc:
            # a changed module the base's templates ran through is likely why
            # the base stopped validating, so that still counts as loosening
            modules = changed_modules(exc.bases, report.changed)
            if exc.source is None or not modules:
                return StrictVerdict(skipped=f"strict mode skipped: {exc}")
            loosened = module_loosenings(modules)
            base_file = exc.source
        else:
            if at_base is None:
                return StrictVerdict()
            modules = tuple(path for path in at_base.modules if path in report.changed)
            if (
                not modules
                and at_base.source == PurePath(config.source.name)
                and at_base.source not in report.changed
            ):
                return StrictVerdict()
            judged = judged_at_base(at_base.config, self.metric_types)
            loosened = loosenings(
                at_base.config,
                config,
                judged=judged,
                scores=Scores(
                    before=self._scores(at_base.config, judged), after=_values(report)
                ),
                modules=modules,
            )
            if not loosened:
                return StrictVerdict()
            base_file = at_base.source
        return StrictVerdict(
            loosened=loosened,
            alongside=self._alongside(
                config,
                read_base=read_base,
                report=report,
                base_file=base_file,
                modules=modules,
            ),
        )

    def _scores(self, base: Config, judged: tuple[MetricSpec, ...]) -> dict[str, int]:
        """Measure the tree as it stands under the base's config."""
        if not judged:
            return {}
        names = tuple(spec.name for spec in judged)
        report = run(
            narrowed(base, Selection(metrics=names)),
            project_tree(self.project_files, base),
            metric_types=self.metric_types,
        )
        return _values(report)

    def _alongside(
        self,
        config: Config,
        *,
        read_base: Callable[[PurePath], bytes | None],
        report: DiffReport,
        base_file: PurePath,
        modules: tuple[PurePath, ...],
    ) -> tuple[PurePath, ...]:
        """Every file the branch changed that is not config."""
        project = project_tree(self.project_files, config)
        files = {PurePath(config.source.name), base_file}
        return tuple(
            path
            for path in report.changed
            if path not in modules
            and not (
                path in files
                and self.store.differs_only_in_config(
                    path, before=read_base(path), after=project.read(path)
                )
            )
        )


def _values(report: RunReport | DiffReport) -> dict[str, int]:
    return {
        outcome.spec.name: outcome.stat.value
        for outcome in report.outcomes
        if outcome.stat is not None
    }
