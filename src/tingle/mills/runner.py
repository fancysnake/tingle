"""Execute configured metrics and collect a RunReport."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, TypeVar

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
    unwatched,
)
from tingle.pacts.report import MetricOutcome, RunReport

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
    from pathlib import PurePath

    from tingle.pacts.config import Config, MetricSpec, RangeSpec
    from tingle.pacts.metrics import ProgressSink

#: What `announced` is counting through. It reports on anything a caller
#: can name, so the runner and the diff runner share it over the two
#: different things they each measure.
ItemT = TypeVar("ItemT")

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
    progress: ProgressSink = unwatched,
) -> RunReport:
    """Run every configured metric, isolating failures per metric."""
    walked = scanned(project, progress)
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
    outcomes = tuple(
        _outcome(spec, context)
        for spec in announced(config.metrics, progress, label=lambda spec: spec.name)
    )
    return RunReport(
        root=config.root, source=config.source, sections=sections(outcomes)
    )


def scanned(project: ProjectFiles, note: ProgressSink) -> tuple[PurePath, ...]:
    """Walk the tree, saying how far it has got as it goes.

    Every so many files rather than every file: a tree is the one part of
    a run with no known size, so the count is the only thing there is to
    report, and reporting each one would cost more than the walk.

    The sort is here rather than in the adapter because this is the first
    point at which draining the walk costs nothing: the counting above it
    has already happened, so the loading screen has been told about the
    tree while it was being read rather than after.

    Shared with the diff runner, which walks the same tree the same way.
    """
    return tuple(sorted(_counted(project.walk(), note)))


def _counted(walk: Iterable[PurePath], note: ProgressSink) -> Iterator[PurePath]:
    """Pass the walk through, reporting the count every so many files."""
    for count, path in enumerate(walk, start=1):
        if count % PROGRESS_EVERY == 0:
            note(RunProgress(RunPhase.SCANNING, done=count))
        yield path


def announced(
    items: Sequence[ItemT], note: ProgressSink, *, label: Callable[[ItemT], str]
) -> Iterator[ItemT]:
    """Hand back each item, naming it before the caller measures it.

    `done` counts what is finished rather than what is running, so it
    never reaches `total` while anything is still going: a run reports
    that it is starting the metric it names.

    Shared with the diff runner, which counts its own measurable metrics
    the same way.
    """
    total = len(items)
    for done, item in enumerate(items):
        note(RunProgress(RunPhase.MEASURING, done=done, total=total, label=label(item)))
        yield item


def _outcome(spec: MetricSpec, context: _RunContext) -> MetricOutcome:
    """Measure one metric, turning a failure into an errored outcome."""
    range_specs, range_names = ranges_for(spec, context.config)
    files = context.ranges.files(range_specs)
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
