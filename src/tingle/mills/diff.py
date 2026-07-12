"""Execute configured metrics against a branch diff."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tingle.mills.display import effective_guide
from tingle.mills.ranges import resolve
from tingle.mills.runner import ranges_for
from tingle.pacts.config import Config, ConfigError, MetricSpec
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
    from collections.abc import Collection, Iterable, Mapping
    from pathlib import PurePath

    from tingle.pacts.config import RangeSpec
    from tingle.pacts.diff import DiffMetricFunction


@dataclass(frozen=True)
class DiffRunner:
    """Runs the diff variant of every configured metric plus its total."""

    config: Config
    project: ProjectFiles
    diff_source: DiffSource
    metric_types: Mapping[str, MetricType]

    def run(self, base: str, only: Collection[str] | None = None) -> DiffReport:
        """Measure the branch impact against merge-base(base, HEAD)."""
        if only is not None:
            known = {spec.name for spec in self.config.metrics}
            if unknown := sorted(set(only) - known):
                raise ConfigError([f'unknown metric "{name}"' for name in unknown])

        branch_diff = self.diff_source.branch_diff(base)
        walked = tuple(self.project.walk())

        outcomes: list[DiffOutcome] = []
        skipped: list[str] = []
        for spec in self.config.metrics:
            if only is not None and spec.name not in only:
                continue
            if (diff_func := self.metric_types[spec.type].diff_func) is None:
                skipped.append(spec.name)
                continue
            outcomes.append(
                self._outcome(spec, diff_func, branch_diff=branch_diff, walked=walked)
            )

        return DiffReport(
            root=self.config.root,
            source=self.config.source,
            base_ref=branch_diff.base_ref,
            merge_base=branch_diff.merge_base,
            outcomes=tuple(outcomes),
            skipped=tuple(skipped),
        )

    def _outcome(
        self,
        spec: MetricSpec,
        diff_func: DiffMetricFunction,
        *,
        branch_diff: BranchDiff,
        walked: tuple[PurePath, ...],
    ) -> DiffOutcome:
        range_specs, range_names = ranges_for(spec, self.config)
        guide = effective_guide(spec, self.config.display)
        diff_context = DiffMetricContext(
            files=_filter_files(branch_diff.files, range_specs),
            read=self.project.read,
            read_base=self.diff_source.read_base,
            params=spec.params,
        )
        total_context = MetricContext(
            files=resolve(walked, range_specs),
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
