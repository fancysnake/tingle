from __future__ import annotations

import dataclasses
from pathlib import Path, PurePath

import pytest

from tingle.pacts.config import Config, ConfigError, MetricSpec, RangeSpec
from tingle.pacts.metrics import MetricContext, MetricResult, MetricType, Occurrence
from tingle.pacts.report import MetricOutcome, RunReport


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
    assert spec.ranges == ()
    assert dict(spec.params) == {}


def test_metric_result_defaults() -> None:
    result = MetricResult(value=3)
    assert dict(result.details) == {}
    assert result.warnings == ()
    assert result.occurrences == ()


def test_occurrence_rendering() -> None:
    assert str(Occurrence(path="src/a.py", line=3)) == "src/a.py:3"
    assert str(Occurrence(path="pyproject.toml", note="E501")) == (
        "pyproject.toml: E501"
    )
    assert str(Occurrence(path="src/a.py")) == "src/a.py"


def test_occurrence_sort_key_handles_missing_fields() -> None:
    occurrences = [
        Occurrence(path="b.py", line=2),
        Occurrence(path="a.py", note="E501"),
        Occurrence(path="a.py", line=5),
        Occurrence(path="a.py"),
    ]

    ordered = sorted(occurrences, key=lambda o: o.sort_key)

    assert [str(o) for o in ordered] == [
        "a.py",
        "a.py: E501",
        "a.py:5",
        "b.py:2",
    ]


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
        spec=spec, range_names=("python",), result=MetricResult(value=0)
    )
    report = RunReport(
        root=Path("/proj"), source=Path("/proj/tingle.toml"), outcomes=(outcome,)
    )
    assert report.outcomes[0].error is None


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
