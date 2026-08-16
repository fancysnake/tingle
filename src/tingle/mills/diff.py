"""Execute configured metrics against a branch diff."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tingle.mills.display import effective_guide, outcome_emoji, sections
from tingle.mills.loc import ProjectLoc
from tingle.mills.ranges import resolve
from tingle.mills.runner import ranges_for, selected
from tingle.mills.text import TextReader, text_reader
from tingle.pacts.config import EVERY_METRIC, Config, MetricSpec, Selection
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
    from collections.abc import Iterable, Mapping

    from tingle.pacts.config import RangeSpec
    from tingle.pacts.diff import DiffMetricFunction


@dataclass(frozen=True)
class _Readers:
    """The two sides a diff metric reads, each adapted from bytes once."""

    current: TextReader
    base: TextReader


@dataclass(frozen=True)
class DiffRunner:
    """Runs the diff variant of every configured metric plus its total."""

    config: Config
    project: ProjectFiles
    diff_source: DiffSource
    metric_types: Mapping[str, MetricType]

    def run(self, base: str, selection: Selection = EVERY_METRIC) -> DiffReport:
        """Measure the branch impact against merge-base(base, HEAD)."""
        specs = selected(self.config, selection)

        branch_diff = self.diff_source.branch_diff(base)
        # both ports hand over bytes; what counts as readable text is
        # decided here, once per side, and never at a call site
        readers = _Readers(
            current=text_reader(self.project.read),
            base=text_reader(self.diff_source.read_base),
        )
        loc = ProjectLoc(
            self.config, read=readers.current, walked=tuple(self.project.walk())
        )

        outcomes: list[DiffOutcome] = []
        skipped: list[str] = []
        for spec in specs:
            if (diff_func := self.metric_types[spec.type].diff_func) is None:
                skipped.append(spec.name)
                continue
            outcomes.append(
                self._outcome(
                    spec, diff_func, branch_diff=branch_diff, loc=loc, readers=readers
                )
            )

        return DiffReport(
            root=self.config.root,
            source=self.config.source,
            base_ref=branch_diff.base_ref,
            merge_base=branch_diff.merge_base,
            sections=sections(tuple(outcomes)),
            skipped=tuple(skipped),
        )

    def _outcome(
        self,
        spec: MetricSpec,
        diff_func: DiffMetricFunction,
        *,
        branch_diff: BranchDiff,
        loc: ProjectLoc,
        readers: _Readers,
    ) -> DiffOutcome:
        range_specs, range_names = ranges_for(spec, self.config)
        guide = effective_guide(spec, self.config.display, loc=loc.lines)
        diff_context = DiffMetricContext(
            files=_filter_files(branch_diff.files, range_specs),
            read=readers.current,
            read_base=readers.base,
            params=spec.params,
        )
        total_context = MetricContext(
            files=resolve(loc.walked, range_specs),
            read=readers.current,
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
