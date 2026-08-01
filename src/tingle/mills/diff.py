"""Execute configured metrics against a branch diff."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tingle.mills.display import effective_guide
from tingle.mills.loc import ProjectLoc
from tingle.mills.ranges import resolve
from tingle.mills.runner import ranges_for, reject_unknown
from tingle.pacts.diff import (
    BranchDiff,
    DiffMetricContext,
    DiffOutcome,
    DiffReport,
    DiffSource,
    FileDiff,
)
from tingle.pacts.metrics import MetricContext, MetricType, ProjectFiles

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Iterator, Mapping

    from tingle.pacts.config import Config, MetricSpec, RangeSpec
    from tingle.pacts.diff import DiffMetricFunction


@dataclass(frozen=True)
class DiffRun:
    """A diff run whose branch is settled but whose metrics are not yet.

    A diff report has a header the config cannot supply -- which branch,
    which merge base, and which metrics have no diff variant to run at
    all -- and a caller drawing rows as they arrive needs it before the
    first of them. Learning it costs a call to git, so it is settled once
    and handed over beside the outcomes rather than trailing them.
    """

    base_ref: str
    merge_base: str
    skipped: tuple[str, ...]
    outcomes: Iterator[DiffOutcome]


@dataclass(frozen=True)
class DiffRunner:
    """Runs the diff variant of every configured metric plus its total."""

    config: Config
    project: ProjectFiles
    diff_source: DiffSource
    metric_types: Mapping[str, MetricType]

    def start(self, base: str, only: Collection[str] | None = None) -> DiffRun:
        """Settle what is being measured against what, and measure nothing.

        The branch is resolved here because the header depends on it.
        Everything after that -- the walk, the line count, every metric --
        waits until the outcomes are pulled.
        """
        reject_unknown(self.config, only)
        branch_diff = self.diff_source.branch_diff(base)
        measured: list[tuple[MetricSpec, DiffMetricFunction]] = []
        skipped: list[str] = []
        for spec in self.config.metrics:
            if only is not None and spec.name not in only:
                continue
            if (diff_func := self.metric_types[spec.type].diff_func) is None:
                skipped.append(spec.name)
            else:
                measured.append((spec, diff_func))
        return DiffRun(
            base_ref=branch_diff.base_ref,
            merge_base=branch_diff.merge_base,
            skipped=tuple(skipped),
            outcomes=self._iter_outcomes(measured, branch_diff),
        )

    def _iter_outcomes(
        self,
        measured: list[tuple[MetricSpec, DiffMetricFunction]],
        branch_diff: BranchDiff,
    ) -> Iterator[DiffOutcome]:
        loc = ProjectLoc(
            self.config, project=self.project, walked=tuple(self.project.walk())
        )
        for spec, diff_func in measured:
            yield self._outcome(spec, diff_func, branch_diff=branch_diff, loc=loc)

    def run(self, base: str, only: Collection[str] | None = None) -> DiffReport:
        """Measure the branch impact against merge-base(base, HEAD)."""
        started = self.start(base, only)
        return DiffReport(
            root=self.config.root,
            source=self.config.source,
            base_ref=started.base_ref,
            merge_base=started.merge_base,
            outcomes=tuple(started.outcomes),
            skipped=started.skipped,
        )

    def _outcome(
        self,
        spec: MetricSpec,
        diff_func: DiffMetricFunction,
        *,
        branch_diff: BranchDiff,
        loc: ProjectLoc,
    ) -> DiffOutcome:
        range_specs, range_names = ranges_for(spec, self.config)
        guide = effective_guide(spec, self.config.display, loc=loc.lines)
        diff_context = DiffMetricContext(
            files=_filter_files(branch_diff.files, range_specs),
            read=self.project.read,
            read_base=self.diff_source.read_base,
            params=spec.params,
        )
        total_context = MetricContext(
            files=resolve(loc.walked, range_specs),
            read=self.project.read,
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
            return DiffOutcome(
                spec=spec,
                range_names=range_names,
                error=f"{type(exc).__name__}: {exc}",
                guide=guide,
            )
        return DiffOutcome(
            spec=spec, range_names=range_names, result=result, total=total, guide=guide
        )


def _filter_files(
    files: Iterable[FileDiff], range_specs: list[RangeSpec]
) -> tuple[FileDiff, ...]:
    """Keep the changed files whose paths match the metric's ranges."""
    candidates = list(files)
    matched = set(resolve((file.path for file in candidates), range_specs))
    return tuple(file for file in candidates if file.path in matched)
