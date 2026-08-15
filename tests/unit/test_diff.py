from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING

import pytest
from support import PROJECT, make_config

from tingle.mills.diff import DiffRunner
from tingle.pacts.config import ConfigError, MetricSpec, RangeSpec
from tingle.pacts.diff import (
    BranchDiff,
    DiffMetricContext,
    DiffResult,
    FileDiff,
    FileStatus,
)
from tingle.pacts.metrics import MetricContext, MetricResult, MetricType

if TYPE_CHECKING:
    from collections.abc import Mapping


class FakeDiffSource:
    def __init__(self, branch: BranchDiff, base: Mapping[str, str]) -> None:
        self._branch = branch
        self._base = dict(base)
        self.requested_base: str | None = None

    def branch_diff(self, base: str) -> BranchDiff:
        self.requested_base = base
        return self._branch

    def read_base(self, path: PurePath) -> bytes | None:
        text = self._base.get(str(path))
        return None if text is None else text.encode()


def _touched_files(ctx: DiffMetricContext) -> DiffResult:
    return DiffResult(net=len(ctx.files), added=len(ctx.files), removed=0)


def _base_lines(ctx: DiffMetricContext) -> DiffResult:
    """Count the base side's lines, which means actually reading it."""
    texts = [ctx.read_base(file.path) for file in ctx.files]
    return DiffResult(net=sum(len(text.splitlines()) for text in texts if text))


def _total_files(ctx: MetricContext) -> MetricResult:
    return MetricResult(value=len(ctx.files))


def _boom_diff(_: DiffMetricContext) -> DiffResult:
    msg = "diff boom"
    raise ValueError(msg)


def _boom_total(_: MetricContext) -> MetricResult:
    msg = "total boom"
    raise ValueError(msg)


METRIC_TYPES = {
    "touched": MetricType(name="touched", func=_total_files, diff_func=_touched_files),
    "boom_diff": MetricType(name="boom_diff", func=_total_files, diff_func=_boom_diff),
    "boom_total": MetricType(
        name="boom_total", func=_boom_total, diff_func=_touched_files
    ),
    "no_diff": MetricType(name="no_diff", func=_total_files),
    "base_lines": MetricType(
        name="base_lines", func=_total_files, diff_func=_base_lines
    ),
}

BRANCH = BranchDiff(
    base_ref="main",
    merge_base="abc123",
    files=(
        FileDiff(
            path=PurePath("a.py"),
            status=FileStatus.MODIFIED,
            added_lines=frozenset({1}),
        ),
        FileDiff(path=PurePath("notes.md"), status=FileStatus.ADDED),
    ),
)


def test_runs_diff_and_total() -> None:
    config = make_config(MetricSpec(name="files", type="touched"))
    source = FakeDiffSource(BRANCH, {})

    report = DiffRunner(config, PROJECT, source, METRIC_TYPES).run("main")

    assert source.requested_base == "main"
    assert report.base_ref == "main"
    assert report.merge_base == "abc123"
    outcome = report.outcomes[0]
    assert outcome.result is not None
    assert outcome.result.net == 1  # notes.md filtered out by the python range
    assert outcome.total is not None
    assert outcome.total.value == 2


def test_the_base_side_reaches_a_metric_as_text_not_as_bytes() -> None:
    """The adapter hands over bytes; the runner decodes on the way in."""
    config = make_config(MetricSpec(name="base", type="base_lines"))
    source = FakeDiffSource(BRANCH, {"a.py": "one\ntwo\nthree\n"})

    report = DiffRunner(config, PROJECT, source, METRIC_TYPES).run("main")

    outcome = report.outcomes[0]
    assert outcome.result is not None
    assert outcome.result.net == 3


def test_range_filtering_applies_to_changed_files() -> None:
    config = make_config(
        MetricSpec(name="all", type="touched", ranges=("everything",)),
        extra_ranges={"everything": RangeSpec(name="everything", include=("**/*",))},
    )

    report = DiffRunner(config, PROJECT, FakeDiffSource(BRANCH, {}), METRIC_TYPES).run(
        "main"
    )

    outcome = report.outcomes[0]
    assert outcome.result is not None
    assert outcome.result.net == 2


def test_raising_diff_func_is_isolated() -> None:
    config = make_config(
        MetricSpec(name="broken", type="boom_diff"),
        MetricSpec(name="files", type="touched"),
    )

    report = DiffRunner(config, PROJECT, FakeDiffSource(BRANCH, {}), METRIC_TYPES).run(
        "main"
    )

    broken, files = report.outcomes
    assert broken.error == "ValueError: diff boom"
    assert broken.result is None
    assert files.result is not None


def test_raising_total_func_is_isolated() -> None:
    config = make_config(MetricSpec(name="broken-total", type="boom_total"))

    report = DiffRunner(config, PROJECT, FakeDiffSource(BRANCH, {}), METRIC_TYPES).run(
        "main"
    )

    assert report.outcomes[0].error == "ValueError: total boom"


def test_type_without_diff_func_is_skipped() -> None:
    config = make_config(
        MetricSpec(name="plain", type="no_diff"),
        MetricSpec(name="files", type="touched"),
    )

    report = DiffRunner(config, PROJECT, FakeDiffSource(BRANCH, {}), METRIC_TYPES).run(
        "main"
    )

    assert report.skipped == ("plain",)
    assert [outcome.spec.name for outcome in report.outcomes] == ["files"]


def test_only_filter() -> None:
    config = make_config(
        MetricSpec(name="first", type="touched"),
        MetricSpec(name="second", type="touched"),
    )

    report = DiffRunner(config, PROJECT, FakeDiffSource(BRANCH, {}), METRIC_TYPES).run(
        "main", only=["second"]
    )

    assert [outcome.spec.name for outcome in report.outcomes] == ["second"]


def test_only_filter_rejects_unknown() -> None:
    config = make_config(MetricSpec(name="files", type="touched"))

    with pytest.raises(ConfigError) as excinfo:
        DiffRunner(config, PROJECT, FakeDiffSource(BRANCH, {}), METRIC_TYPES).run(
            "main", only=["nope"]
        )

    assert 'unknown metric "nope"' in excinfo.value.errors
