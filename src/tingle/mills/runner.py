"""Execute configured metrics and collect a RunReport."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from tingle.mills.ranges import resolve
from tingle.pacts.config import Config, ConfigError, MetricSpec, RangeSpec
from tingle.pacts.metrics import MetricContext, MetricType, ProjectFiles
from tingle.pacts.report import MetricOutcome, RunReport

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping


def run(
    config: Config,
    project: ProjectFiles,
    metric_types: Mapping[str, MetricType],
    only: Collection[str] | None = None,
) -> RunReport:
    """Run every configured metric, isolating failures per metric."""
    if only is not None:
        known = {spec.name for spec in config.metrics}
        unknown = sorted(set(only) - known)
        if unknown:
            raise ConfigError([f'unknown metric "{name}"' for name in unknown])

    walked = tuple(project.walk())
    outcomes: list[MetricOutcome] = []
    for spec in config.metrics:
        if only is not None and spec.name not in only:
            continue

        range_specs, range_names = ranges_for(spec, config)
        files = resolve(walked, range_specs)
        context = MetricContext(
            files=files, read=project.read, exists=project.exists, params=spec.params
        )
        try:
            result = metric_types[spec.type].func(context)
        except Exception as exc:  # metric isolation: one failure must not stop the run
            outcomes.append(
                MetricOutcome(
                    spec=spec,
                    range_names=range_names,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            continue

        if not files and spec.ranges:
            result = replace(
                result, warnings=(*result.warnings, "ranges matched no files")
            )
        outcomes.append(
            MetricOutcome(spec=spec, range_names=range_names, result=result)
        )

    return RunReport(root=config.root, source=config.source, outcomes=tuple(outcomes))


def ranges_for(
    spec: MetricSpec, config: Config
) -> tuple[list[RangeSpec], tuple[str, ...]]:
    """Resolve a metric's range specs and display names (default applies)."""
    if spec.ranges:
        return [config.ranges[name] for name in spec.ranges], spec.ranges
    return [config.default_range], (config.default_range.name,)
