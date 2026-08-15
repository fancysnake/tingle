from __future__ import annotations

import dataclasses
from pathlib import Path, PurePath

import pytest

from tingle.pacts.config import Config, ConfigError, MetricSpec, RangeSpec
from tingle.pacts.metrics import MetricContext, MetricResult, MetricType, Occurrence
from tingle.pacts.report import (
    GroupSummary,
    MetricOutcome,
    ReportSection,
    RunReport,
    Stat,
)


def test_config_error_aggregates_messages() -> None:
    error = ConfigError(["first problem", "second problem"])
    assert error.errors == ["first problem", "second problem"]
    assert "first problem" in str(error)
    assert "second problem" in str(error)


def test_range_spec_is_immutable() -> None:
    spec = RangeSpec(name="python", include=("src/**/*.py",))
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.name = "other"  # type: ignore[misc]


def test_metric_spec_defaults() -> None:
    spec = MetricSpec(name="noqa", type="regex_count")
    assert not spec.ranges
    assert not spec.params


def test_metric_result_defaults() -> None:
    result = MetricResult(value=3)
    assert not result.details
    assert not result.warnings
    assert not result.occurrences


def test_occurrence_rendering() -> None:
    assert str(Occurrence(path="src/a.py", line=3)) == "src/a.py:3"
    assert str(Occurrence(path="pyproject.toml", note="E501")) == (
        "pyproject.toml: E501"
    )
    assert str(Occurrence(path="src/a.py")) == "src/a.py"


def test_occurrence_is_immutable() -> None:
    occurrence = Occurrence(path="a.py", line=1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        occurrence.line = 2  # type: ignore[misc]


def test_metric_type_holds_function() -> None:
    def fn(ctx: MetricContext) -> MetricResult:
        return MetricResult(value=len(ctx.files))

    metric_type = MetricType(name="file_count", func=fn)
    context = MetricContext(
        files=(PurePath("a.py"),),
        read=lambda _: None,
        exists=lambda _: False,
        params={},
    )
    assert metric_type.func(context).value == 1


def test_run_report_construction() -> None:
    spec = MetricSpec(name="noqa", type="regex_count")
    outcome = MetricOutcome(
        spec=spec, range_names=("python",), emoji="🎉", result=MetricResult(value=0)
    )
    report = RunReport(
        root=Path("/proj"),
        source=Path("/proj/tingle.toml"),
        sections=(
            ReportSection(
                name=None,
                outcomes=(outcome,),
                summary=GroupSummary(value=0, guide=100, emoji="🎉"),
            ),
        ),
    )
    # the outcomes a report answers with are the ones its sections hold
    assert report.outcomes == (outcome,)
    assert report.outcomes[0].error is None


def test_a_metric_that_failed_has_nothing_for_a_view_to_show() -> None:
    """The one question a view asks: is there a number and a rank for it.

    A metric that raised answers no, so the rank it was built with is
    never read and cannot be mistaken for a judgement of its own.
    """
    spec = MetricSpec(name="noqa", type="regex_count")
    failed = MetricOutcome.errored(
        spec, range_names=(), guide=100, exc=ValueError("boom")
    )

    assert failed.stat is None
    assert failed.error == "ValueError: boom"
    assert MetricOutcome(
        spec=spec, range_names=(), emoji="🎉", result=MetricResult(value=3)
    ).stat == Stat(emoji="🎉", value=3)


def test_config_construction() -> None:
    python_range = RangeSpec(name="python", include=("**/*.py",), default=True)
    config = Config(
        root=Path("/proj"),
        source=Path("/proj/tingle.toml"),
        ranges={"python": python_range},
        metrics=(MetricSpec(name="noqa", type="regex_count"),),
        default_range=python_range,
    )
    assert config.default_range.name == "python"
