"""Execute configured metrics and collect a RunReport."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from tingle.mills.display import effective_guide
from tingle.mills.ranges import resolve
from tingle.pacts.config import Config, ConfigError, MetricSpec, RangeSpec
from tingle.pacts.metrics import MetricContext, MetricType, ProjectFiles
from tingle.pacts.report import MetricOutcome, RunReport

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping
    from pathlib import PurePath


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
    outcomes = tuple(
        _outcome(
            spec, config, project=project, metric_types=metric_types, walked=walked
        )
        for spec in config.metrics
        if only is None or spec.name in only
    )
    return RunReport(root=config.root, source=config.source, outcomes=outcomes)


def _outcome(
    spec: MetricSpec,
    config: Config,
    *,
    project: ProjectFiles,
    metric_types: Mapping[str, MetricType],
    walked: tuple[PurePath, ...],
) -> MetricOutcome:
    """Measure one metric, turning a failure into an errored outcome."""
    range_specs, range_names = ranges_for(spec, config)
    files = resolve(walked, range_specs)
    guide = effective_guide(spec, config.display)
    context = MetricContext(
        files=files, read=project.read, exists=project.exists, params=spec.params
    )
    try:
        result = metric_types[spec.type].func(context)
    # metric isolation: one failure must not stop the run
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return MetricOutcome(
            spec=spec,
            range_names=range_names,
            error=f"{type(exc).__name__}: {exc}",
            guide=guide,
        )

    if not files and spec.ranges:
        result = replace(result, warnings=(*result.warnings, "ranges matched no files"))
    return MetricOutcome(spec=spec, range_names=range_names, result=result, guide=guide)


def ranges_for(
    spec: MetricSpec, config: Config
) -> tuple[list[RangeSpec], tuple[str, ...]]:
    """Resolve a metric's range specs and display names (default applies)."""
    if spec.ranges:
        return [config.ranges[name] for name in spec.ranges], spec.ranges
    return [config.default_range], (config.default_range.name,)
