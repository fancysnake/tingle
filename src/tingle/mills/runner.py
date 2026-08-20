"""Execute configured metrics and collect a RunReport."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from tingle.mills.display import effective_guide, outcome_emoji, sections
from tingle.mills.loc import ProjectLoc
from tingle.mills.ranges import ResolvedRanges
from tingle.mills.text import TextReader, text_reader
from tingle.pacts.metrics import (
    MetricContext,
    MetricType,
    ProjectFiles,
    RunPhase,
    RunProgress,
)
from tingle.pacts.report import MetricOutcome, RunReport

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from pathlib import PurePath

    from tingle.pacts.config import Config, MetricSpec, RangeSpec
    from tingle.pacts.metrics import ProgressSink

#: How many files the walk gets through between saying so. A tree is the
#: one part of a run whose size is unknown until it ends, so this trades
#: how smoothly that reads against what saying it costs.
PROGRESS_EVERY = 500


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
    ranges: ResolvedRanges


def run(
    config: Config,
    project: ProjectFiles,
    *,
    metric_types: Mapping[str, MetricType],
    progress: ProgressSink | None = None,
) -> RunReport:
    """Run every configured metric, isolating failures per metric."""
    note = watcher(progress)
    walked = tuple(scanned(project, note))
    # the port hands over bytes; what counts as readable text is decided
    # here, once, and every metric is given the same reader
    read = text_reader(project.read)
    ranges = ResolvedRanges(walked)
    context = _RunContext(
        config=config,
        project=project,
        read=read,
        metric_types=metric_types,
        loc=ProjectLoc(config, read=read, ranges=ranges),
        ranges=ranges,
    )
    outcomes = tuple(_measured(config, context, note=note))
    return RunReport(
        root=config.root, source=config.source, sections=sections(outcomes)
    )


def _measured(
    config: Config, context: _RunContext, *, note: ProgressSink
) -> Iterator[MetricOutcome]:
    """Measure each metric, saying which one is starting before it does."""
    total = len(config.metrics)
    for done, spec in enumerate(config.metrics):
        note(RunProgress(RunPhase.MEASURING, done=done, total=total, label=spec.name))
        yield _outcome(spec, context)


def scanned(project: ProjectFiles, note: ProgressSink) -> Iterator[PurePath]:
    """Walk the tree, saying how far it has got as it goes.

    Every so many files rather than every file: a tree is the one part of
    a run with no known size, so the count is the only thing there is to
    report, and reporting each one would cost more than the walk.

    Shared with the diff runner, which walks the same tree the same way.
    """
    for count, path in enumerate(project.walk(), start=1):
        if count % PROGRESS_EVERY == 0:
            note(RunProgress(RunPhase.SCANNING, done=count))
        yield path


def watcher(progress: ProgressSink | None) -> ProgressSink:
    """Return the sink a run reports to: the caller's, or one that drops it.

    Normalising here is what lets every runner say `note(...)` outright
    rather than guarding each report, and what keeps a run nobody is
    watching -- which is all of them but the interactive one -- paying
    nothing but a call.
    """
    return progress if progress is not None else _unwatched


def _unwatched(_: RunProgress) -> None:
    """Take the progress of a run nobody is watching, and drop it."""


def _outcome(spec: MetricSpec, context: _RunContext) -> MetricOutcome:
    """Measure one metric, turning a failure into an errored outcome."""
    range_specs, range_names = ranges_for(spec, context.config)
    files = context.ranges.files(range_names, range_specs)
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
