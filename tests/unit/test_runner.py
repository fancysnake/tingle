from __future__ import annotations

from pathlib import Path, PurePath
from typing import TYPE_CHECKING

import pytest

from tingle.mills.runner import run
from tingle.pacts.config import (
    DEFAULT_GUIDE,
    Config,
    ConfigError,
    DisplaySpec,
    MetricSpec,
    RangeSpec,
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


def _file_count(ctx: MetricContext) -> MetricResult:
    return MetricResult(value=len(ctx.files))


def _boom(_: MetricContext) -> MetricResult:
    msg = "boom"
    raise ValueError(msg)


METRIC_TYPES = {
    "file_count": MetricType(name="file_count", func=_file_count),
    "boom": MetricType(name="boom", func=_boom),
}

PYTHON_RANGE = RangeSpec(name="python", include=("**/*.py",), default=True)


def _config(*metrics: MetricSpec) -> Config:
    return Config(
        root=Path("/proj"),
        source=Path("/proj/tingle.toml"),
        ranges={"python": PYTHON_RANGE},
        metrics=metrics,
        default_range=PYTHON_RANGE,
    )


PROJECT = FakeProject({"a.py": "", "b.py": "", "notes.md": ""})


def test_runs_metrics_and_reports_values() -> None:
    config = _config(MetricSpec(name="files", type="file_count", ranges=("python",)))

    report = run(config, PROJECT, metric_types=METRIC_TYPES)

    outcome = report.outcomes[0]
    assert outcome.result is not None
    assert outcome.result.value == 2
    assert outcome.range_names == ("python",)
    assert outcome.error is None


def test_default_range_applies_when_none_given() -> None:
    config = _config(MetricSpec(name="files", type="file_count"))

    report = run(config, PROJECT, metric_types=METRIC_TYPES)

    outcome = report.outcomes[0]
    assert outcome.result is not None
    assert outcome.result.value == 2
    assert outcome.range_names == ("python",)


def test_raising_metric_is_isolated() -> None:
    config = _config(
        MetricSpec(name="broken", type="boom"),
        MetricSpec(name="files", type="file_count"),
    )

    report = run(config, PROJECT, metric_types=METRIC_TYPES)

    broken, files = report.outcomes
    assert broken.result is None
    assert broken.error == "ValueError: boom"
    assert files.result is not None
    assert files.result.value == 2


def test_empty_explicit_ranges_warn() -> None:
    empty = RangeSpec(name="empty", include=("nothing/**",))
    config = Config(
        root=Path("/proj"),
        source=Path("/proj/tingle.toml"),
        ranges={"python": PYTHON_RANGE, "empty": empty},
        metrics=(MetricSpec(name="files", type="file_count", ranges=("empty",)),),
        default_range=PYTHON_RANGE,
    )

    report = run(config, PROJECT, metric_types=METRIC_TYPES)

    outcome = report.outcomes[0]
    assert outcome.result is not None
    assert outcome.result.value == 0
    assert "ranges matched no files" in outcome.result.warnings


def test_only_filter_selects_metrics() -> None:
    config = _config(
        MetricSpec(name="first", type="file_count"),
        MetricSpec(name="second", type="file_count"),
    )

    report = run(config, PROJECT, metric_types=METRIC_TYPES, only=["second"])

    assert [outcome.spec.name for outcome in report.outcomes] == ["second"]


def test_only_filter_rejects_unknown_names() -> None:
    config = _config(MetricSpec(name="files", type="file_count"))

    with pytest.raises(ConfigError) as excinfo:
        run(config, PROJECT, metric_types=METRIC_TYPES, only=["nope"])

    assert 'unknown metric "nope"' in excinfo.value.errors


def _config_with_display(display: DisplaySpec, *metrics: MetricSpec) -> Config:
    return Config(
        root=Path("/proj"),
        source=Path("/proj/tingle.toml"),
        ranges={"python": PYTHON_RANGE},
        metrics=metrics,
        default_range=PYTHON_RANGE,
        display=display,
    )


def test_outcome_carries_the_global_guide_when_the_metric_sets_none() -> None:
    config = _config_with_display(
        DisplaySpec(guide=25), MetricSpec(name="files", type="file_count")
    )

    report = run(config, PROJECT, metric_types=METRIC_TYPES)

    assert report.outcomes[0].guide == 25


def test_outcome_carries_the_metric_guide_over_the_global_one() -> None:
    config = _config_with_display(
        DisplaySpec(guide=25), MetricSpec(name="files", type="file_count", guide=5)
    )

    report = run(config, PROJECT, metric_types=METRIC_TYPES)

    assert report.outcomes[0].guide == 5


def test_outcome_falls_back_to_the_default_guide() -> None:
    config = _config(MetricSpec(name="files", type="file_count"))

    report = run(config, PROJECT, metric_types=METRIC_TYPES)

    assert report.outcomes[0].guide == DEFAULT_GUIDE


def test_a_failed_metric_still_carries_its_guide() -> None:
    """The error row is rendered like any other, so it needs a guide too."""
    config = _config_with_display(
        DisplaySpec(guide=25), MetricSpec(name="bad", type="boom", guide=7)
    )

    report = run(config, PROJECT, metric_types=METRIC_TYPES)

    outcome = report.outcomes[0]
    assert outcome.error is not None
    assert outcome.guide == 7
