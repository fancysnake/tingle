"""Execute configured metrics and collect a RunReport."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from tingle.mills.display import effective_guide, outcome_emoji, sections
from tingle.mills.loc import ProjectLoc
from tingle.mills.ranges import resolve
from tingle.mills.text import TextReader, text_reader
from tingle.pacts.config import (
    EVERY_METRIC,
    Config,
    ConfigError,
    MetricSpec,
    RangeSpec,
    Selection,
)
from tingle.pacts.metrics import MetricContext, MetricType, ProjectFiles
from tingle.pacts.report import MetricOutcome, RunReport

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True)
class _RunContext:
    """What every metric in one run is measured against.

    Built once and handed down whole: none of it varies by metric, and
    threading each piece separately is what grows the signature.
    """

    config: Config
    project: ProjectFiles
    read: TextReader
    metric_types: Mapping[str, MetricType]
    loc: ProjectLoc


def selected(config: Config, selection: Selection) -> tuple[MetricSpec, ...]:
    """Narrow the config's metrics to the ones a selection asks for.

    Every name is checked before anything runs, and both axes report at
    once: a command line that misspelled a metric and a group is told
    about both rather than about whichever was looked at first.
    """
    if selection.everything:
        return config.metrics
    names = {spec.name for spec in config.metrics}
    groups = {spec.group for spec in config.metrics if spec.group is not None}
    errors = [
        f'unknown metric "{name}"' for name in sorted(set(selection.metrics) - names)
    ] + [f'unknown group "{name}"' for name in sorted(set(selection.groups) - groups)]
    if errors:
        raise ConfigError(errors)
    return tuple(
        spec
        for spec in config.metrics
        if spec.name in selection.metrics or spec.group in selection.groups
    )


def run(
    config: Config,
    project: ProjectFiles,
    *,
    metric_types: Mapping[str, MetricType],
    selection: Selection = EVERY_METRIC,
) -> RunReport:
    """Run every selected metric, isolating failures per metric."""
    specs = selected(config, selection)

    walked = tuple(project.walk())
    # the port hands over bytes; what counts as readable text is decided
    # here, once, and every metric is given the same reader
    read = text_reader(project.read)
    context = _RunContext(
        config=config,
        project=project,
        read=read,
        metric_types=metric_types,
        loc=ProjectLoc(config, read=read, walked=walked),
    )
    outcomes = tuple(_outcome(spec, context) for spec in specs)
    return RunReport(
        root=config.root, source=config.source, sections=sections(outcomes)
    )


def _outcome(spec: MetricSpec, context: _RunContext) -> MetricOutcome:
    """Measure one metric, turning a failure into an errored outcome."""
    range_specs, range_names = ranges_for(spec, context.config)
    files = resolve(context.loc.walked, range_specs)
    guide = effective_guide(spec, context.config.display, loc=context.loc.lines)
    metric_context = MetricContext(
        files=files,
        read=context.read,
        exists=context.project.exists,
        params=spec.params,
    )
    try:
        result = context.metric_types[spec.type].func(metric_context)
    # metric isolation: one failure must not stop the run
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return MetricOutcome.errored(
            spec, range_names=range_names, guide=guide, exc=exc
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


def ranges_for(
    spec: MetricSpec, config: Config
) -> tuple[list[RangeSpec], tuple[str, ...]]:
    """Resolve a metric's range specs and display names (default applies)."""
    if spec.ranges:
        return [config.ranges[name] for name in spec.ranges], spec.ranges
    return [config.default_range], (config.default_range.name,)
