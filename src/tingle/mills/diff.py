"""Execute configured metrics against a branch diff."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tingle.mills.display import effective_guide, outcome_emoji, sections
from tingle.mills.loc import ProjectLoc
from tingle.mills.ranges import ResolvedRanges, resolve
from tingle.mills.runner import announced, ranges_for, scanned
from tingle.mills.text import TextReader, text_reader
from tingle.pacts.diff import (
    BranchDiff,
    DiffMetricContext,
    DiffOutcome,
    DiffReport,
    DiffSource,
    FileDiff,
)
from tingle.pacts.metrics import (
    MetricContext,
    MetricType,
    ProjectFiles,
    RunPhase,
    RunProgress,
    unwatched,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from tingle.pacts.config import Config, MetricSpec, RangeSpec
    from tingle.pacts.diff import DiffMetricFunction
    from tingle.pacts.metrics import ProgressSink


@dataclass(frozen=True)
class _Readers:
    """The two sides a diff metric reads, each adapted from bytes once."""

    current: TextReader
    base: TextReader


@dataclass(frozen=True)
class _DiffContext:
    """What every metric in one diff run is measured against.

    Built once and handed down whole, the way a full run's context is:
    none of it varies by metric, and threading each piece separately is
    what grows the signature.
    """

    branch_diff: BranchDiff
    readers: _Readers
    loc: ProjectLoc
    ranges: ResolvedRanges


@dataclass(frozen=True)
class DiffRunner:
    """Runs the diff variant of every configured metric plus its total."""

    config: Config
    project: ProjectFiles
    diff_source: DiffSource
    metric_types: Mapping[str, MetricType]

    def run(self, base: str, *, progress: ProgressSink = unwatched) -> DiffReport:
        """Measure the branch impact against merge-base(base, HEAD)."""
        progress(RunProgress(RunPhase.DIFFING, label=base))
        branch_diff = self.diff_source.branch_diff(base)
        # both ports hand over bytes; what counts as readable text is
        # decided here, once per side, and never at a call site
        readers = _Readers(
            current=text_reader(self.project.read),
            base=text_reader(self.diff_source.read_base),
        )
        ranges = ResolvedRanges(scanned(self.project, progress))
        context = _DiffContext(
            branch_diff=branch_diff,
            readers=readers,
            loc=ProjectLoc(self.config, read=readers.current, ranges=ranges),
            ranges=ranges,
        )

        # a metric with no diff variant is skipped rather than measured, so
        # the two are sorted out before anything runs: what the bar counts
        # has to be the metrics that will actually take time
        measurable: list[tuple[MetricSpec, DiffMetricFunction]] = []
        skipped: list[str] = []
        for spec in self.config.metrics:
            if (diff_func := self.metric_types[spec.type].diff_func) is None:
                skipped.append(spec.name)
            else:
                measurable.append((spec, diff_func))

        outcomes = tuple(
            self._outcome(spec, diff_func, context=context)
            for spec, diff_func in announced(
                measurable, progress, label=lambda pair: pair[0].name
            )
        )

        return DiffReport(
            root=self.config.root,
            source=self.config.source,
            base_ref=branch_diff.base_ref,
            merge_base=branch_diff.merge_base,
            sections=sections(outcomes),
            skipped=tuple(skipped),
        )

    def _outcome(
        self, spec: MetricSpec, diff_func: DiffMetricFunction, *, context: _DiffContext
    ) -> DiffOutcome:
        range_specs, range_names = ranges_for(spec, self.config)
        guide = effective_guide(spec, self.config.display, loc=context.loc.lines)
        diff_context = DiffMetricContext(
            files=_filter_files(context.branch_diff.files, range_specs),
            read=context.readers.current,
            read_base=context.readers.base,
            params=spec.params,
        )
        total_context = MetricContext(
            files=context.ranges.files(range_specs),
            read=context.readers.current,
            exists=self.project.exists,
            params=spec.params,
        )
        try:
            # metric isolation: a failure must not stop the run, so any
            # exception a metric function raises is caught and reported
            result, total = (
                diff_func(diff_context),
                self.metric_types[spec.type].func(total_context),
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            return DiffOutcome.errored(
                spec, range_names=range_names, guide=guide, exc=exc
            )
        return DiffOutcome(
            spec=spec,
            range_names=range_names,
            emoji=outcome_emoji(total, guide),
            result=result,
            total=total,
            guide=guide,
        )


def _filter_files(
    files: Iterable[FileDiff], range_specs: list[RangeSpec]
) -> tuple[FileDiff, ...]:
    """Keep the changed files whose paths match the metric's ranges."""
    candidates = list(files)
    matched = set(resolve((file.path for file in candidates), range_specs))
    return tuple(file for file in candidates if file.path in matched)
