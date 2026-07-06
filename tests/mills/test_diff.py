from __future__ import annotations

from pathlib import Path, PurePath
from typing import TYPE_CHECKING

import pytest

from tingle.mills.diff import DiffRunner
from tingle.pacts.config import Config, ConfigError, MetricSpec, RangeSpec
from tingle.pacts.diff import (
    BranchDiff,
    DiffMetricContext,
    DiffResult,
    FileDiff,
    FileStatus,
)
from tingle.pacts.metrics import MetricContext, MetricResult, MetricType

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


class FakeProject:
    def __init__(self, contents: Mapping[str, str]) -> None:
        self._contents = dict(contents)

    def walk(self) -> Iterable[PurePath]:
        return sorted(PurePath(name) for name in self._contents)

    def read(self, path: PurePath) -> str | None:
        return self._contents.get(str(path))

    def exists(self, path: PurePath) -> bool:
        return str(path) in self._contents


class FakeDiffSource:
    def __init__(self, branch: BranchDiff, base: Mapping[str, str]) -> None:
        self._branch = branch
        self._base = dict(base)
        self.requested_base: str | None = None

    def branch_diff(self, base: str) -> BranchDiff:
        self.requested_base = base
        return self._branch

    def read_base(self, path: PurePath) -> str | None:
        return self._base.get(str(path))


def _touched_files(ctx: DiffMetricContext) -> DiffResult:
    return DiffResult(net=len(ctx.files), added=len(ctx.files), removed=0)


def _total_files(ctx: MetricContext) -> MetricResult:
    return MetricResult(value=len(ctx.files))


def _boom_diff(_: DiffMetricContext) -> DiffResult:
    msg = "diff boom"
    raise ValueError(msg)


def _boom_total(_: MetricContext) -> MetricResult:
    msg = "total boom"
    raise ValueError(msg)


METRIC_TYPES = {
    "touched": MetricType(
        name="touched", func=_total_files, diff_func=_touched_files
    ),
    "boom_diff": MetricType(
        name="boom_diff", func=_total_files, diff_func=_boom_diff
    ),
    "boom_total": MetricType(
        name="boom_total", func=_boom_total, diff_func=_touched_files
    ),
    "no_diff": MetricType(name="no_diff", func=_total_files),
}

PYTHON_RANGE = RangeSpec(name="python", include=("**/*.py",), default=True)

PROJECT = FakeProject({"a.py": "", "b.py": "", "notes.md": ""})

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


def _config(*metrics: MetricSpec) -> Config:
    return Config(
        root=Path("/proj"),
        source=Path("/proj/tingle.toml"),
        ranges={"python": PYTHON_RANGE},
        metrics=metrics,
        default_range=PYTHON_RANGE,
    )


def test_runs_diff_and_total() -> None:
    config = _config(MetricSpec(name="files", type="touched"))
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


def test_range_filtering_applies_to_changed_files() -> None:
    everything = RangeSpec(name="everything", include=("**/*",))
    config = Config(
        root=Path("/proj"),
        source=Path("/proj/tingle.toml"),
        ranges={"python": PYTHON_RANGE, "everything": everything},
        metrics=(
            MetricSpec(name="all", type="touched", ranges=("everything",)),
        ),
        default_range=PYTHON_RANGE,
    )

    report = DiffRunner(
        config, PROJECT, FakeDiffSource(BRANCH, {}), METRIC_TYPES
    ).run("main")

    outcome = report.outcomes[0]
    assert outcome.result is not None
    assert outcome.result.net == 2


def test_raising_diff_func_is_isolated() -> None:
    config = _config(
        MetricSpec(name="broken", type="boom_diff"),
        MetricSpec(name="files", type="touched"),
    )

    report = DiffRunner(
        config, PROJECT, FakeDiffSource(BRANCH, {}), METRIC_TYPES
    ).run("main")

    broken, files = report.outcomes
    assert broken.error == "ValueError: diff boom"
    assert broken.result is None
    assert files.result is not None


def test_raising_total_func_is_isolated() -> None:
    config = _config(MetricSpec(name="broken-total", type="boom_total"))

    report = DiffRunner(
        config, PROJECT, FakeDiffSource(BRANCH, {}), METRIC_TYPES
    ).run("main")

    assert report.outcomes[0].error == "ValueError: total boom"


def test_type_without_diff_func_is_skipped() -> None:
    config = _config(
        MetricSpec(name="plain", type="no_diff"),
        MetricSpec(name="files", type="touched"),
    )

    report = DiffRunner(
        config, PROJECT, FakeDiffSource(BRANCH, {}), METRIC_TYPES
    ).run("main")

    assert report.skipped == ("plain",)
    assert [outcome.spec.name for outcome in report.outcomes] == ["files"]


def test_only_filter() -> None:
    config = _config(
        MetricSpec(name="first", type="touched"),
        MetricSpec(name="second", type="touched"),
    )

    report = DiffRunner(
        config, PROJECT, FakeDiffSource(BRANCH, {}), METRIC_TYPES
    ).run("main", only=["second"])

    assert [outcome.spec.name for outcome in report.outcomes] == ["second"]


def test_only_filter_rejects_unknown() -> None:
    config = _config(MetricSpec(name="files", type="touched"))

    with pytest.raises(ConfigError) as excinfo:
        DiffRunner(
            config, PROJECT, FakeDiffSource(BRANCH, {}), METRIC_TYPES
        ).run("main", only=["nope"])

    assert 'unknown metric "nope"' in excinfo.value.errors
