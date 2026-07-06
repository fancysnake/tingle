from __future__ import annotations

import dataclasses
from pathlib import Path, PurePath

import pytest

from tingle.pacts.config import MetricSpec
from tingle.pacts.diff import (
    BranchDiff,
    DiffMetricContext,
    DiffOutcome,
    DiffReport,
    DiffResult,
    FileDiff,
    FileStatus,
)
from tingle.pacts.metrics import MetricContext, MetricResult, MetricType


def test_file_diff_defaults_to_empty_line_sets() -> None:
    diff = FileDiff(path=PurePath("a.py"), status=FileStatus.MODIFIED)

    assert diff.added_lines == frozenset()
    assert diff.removed_lines == frozenset()


def test_file_diff_is_immutable() -> None:
    diff = FileDiff(path=PurePath("a.py"), status=FileStatus.ADDED)

    with pytest.raises(dataclasses.FrozenInstanceError):
        diff.status = FileStatus.DELETED  # type: ignore[misc]


def test_diff_result_value_delta_shape() -> None:
    result = DiffResult(net=2)

    assert result.added is None
    assert result.removed is None
    assert dict(result.details) == {}


def test_metric_type_diff_func_defaults_to_none() -> None:
    def fn(ctx: MetricContext) -> MetricResult:
        return MetricResult(value=len(ctx.files))

    assert MetricType(name="file_count", func=fn).diff_func is None


def test_metric_type_accepts_diff_func() -> None:
    def fn(ctx: MetricContext) -> MetricResult:
        return MetricResult(value=len(ctx.files))

    def diff_fn(ctx: DiffMetricContext) -> DiffResult:
        return DiffResult(net=len(ctx.files), added=len(ctx.files), removed=0)

    metric_type = MetricType(name="file_count", func=fn, diff_func=diff_fn)
    context = DiffMetricContext(
        files=(FileDiff(path=PurePath("a.py"), status=FileStatus.ADDED),),
        read=lambda _: None,
        read_base=lambda _: None,
        params={},
    )

    assert metric_type.diff_func is not None
    assert metric_type.diff_func(context).net == 1


def test_diff_report_construction() -> None:
    spec = MetricSpec(name="noqa", type="regex_count")
    outcome = DiffOutcome(
        spec=spec,
        range_names=("python",),
        result=DiffResult(net=1, added=2, removed=1),
        total=MetricResult(value=10),
    )
    report = DiffReport(
        root=Path("/proj"),
        source=Path("/proj/tingle.toml"),
        base_ref="main",
        merge_base="abc123",
        outcomes=(outcome,),
    )

    branch_diff = BranchDiff(base_ref="main", merge_base="abc123", files=())
    assert branch_diff.files == ()
    assert report.outcomes[0].total is not None
    assert report.outcomes[0].total.value == 10
