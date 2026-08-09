"""Execute configured metrics and collect a RunReport."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, TypeVar

from tingle.mills.display import effective_guide, outcome_emoji, sections
from tingle.mills.loc import ProjectLoc
from tingle.mills.ranges import resolve
from tingle.mills.text import text_reader
from tingle.pacts.config import Config, ConfigError, MetricSpec, RangeSpec
from tingle.pacts.metrics import MetricContext, MetricType, ProjectFiles
from tingle.pacts.report import MetricOutcome, RunReport

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from tingle.pacts.diff import DiffOutcome

_Outcome = TypeVar("_Outcome", bound="MetricOutcome | DiffOutcome")


def run(
    config: Config,
    project: ProjectFiles,
    *,
    metric_types: Mapping[str, MetricType],
    only: Collection[str] | None = None,
) -> RunReport:
    """Run every configured metric, isolating failures per metric."""
    if only is not None:
        known = {spec.name for spec in config.metrics}
        if unknown := sorted(set(only) - known):
            raise ConfigError([f'unknown metric "{name}"' for name in unknown])

    walked = tuple(project.walk())
    loc = ProjectLoc(config, project=project, walked=walked)
    outcomes = tuple(
        _outcome(spec, config, project=project, metric_types=metric_types, loc=loc)
        for spec in config.metrics
        if only is None or spec.name in only
    )
    return RunReport(
        root=config.root, source=config.source, sections=sections(outcomes)
    )


def _outcome(
    spec: MetricSpec,
    config: Config,
    *,
    project: ProjectFiles,
    metric_types: Mapping[str, MetricType],
    loc: ProjectLoc,
) -> MetricOutcome:
    """Measure one metric, turning a failure into an errored outcome."""
    range_specs, range_names = ranges_for(spec, config)
    files = resolve(loc.walked, range_specs)
    guide = effective_guide(spec, config.display, loc=loc.lines)
    context = MetricContext(
        files=files,
        read=text_reader(project.read),
        exists=project.exists,
        params=spec.params,
    )
    try:
        result = metric_types[spec.type].func(context)
    # metric isolation: one failure must not stop the run
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return errored(
            MetricOutcome, spec, range_names=range_names, guide=guide, exc=exc
        )

    if not files and spec.ranges:
        result = replace(result, warnings=(*result.warnings, "ranges matched no files"))
    return MetricOutcome(
        spec=spec,
        range_names=range_names,
        emoji=outcome_emoji(result, guide),
        result=result,
        guide=guide,
    )


def errored(
    kind: type[_Outcome],
    spec: MetricSpec,
    *,
    range_names: tuple[str, ...],
    guide: int,
    exc: Exception,
) -> _Outcome:
    """Report a metric that raised: the reason kept, and nothing ranked.

    A run and a diff isolate their metrics the same way and say the same
    thing about one that failed, so they say it in one place; only the
    kind of outcome they hand back differs.
    """
    return kind(
        spec=spec,
        range_names=range_names,
        emoji="",
        error=f"{type(exc).__name__}: {exc}",
        guide=guide,
    )


def ranges_for(
    spec: MetricSpec, config: Config
) -> tuple[list[RangeSpec], tuple[str, ...]]:
    """Resolve a metric's range specs and display names (default applies)."""
    if spec.ranges:
        return [config.ranges[name] for name in spec.ranges], spec.ranges
    return [config.default_range], (config.default_range.name,)
