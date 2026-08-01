from __future__ import annotations

import pytest
from support import PROJECT, FakeProject, WatchfulProject, make_config

from tingle.mills.runner import iter_outcomes, run
from tingle.pacts.config import ConfigError, DisplaySpec, MetricSpec, RangeSpec
from tingle.pacts.metrics import MetricContext, MetricResult, MetricType


def _file_count(ctx: MetricContext) -> MetricResult:
    return MetricResult(value=len(ctx.files))


def _boom(_: MetricContext) -> MetricResult:
    msg = "boom"
    raise ValueError(msg)


METRIC_TYPES = {
    "file_count": MetricType(name="file_count", func=_file_count),
    "boom": MetricType(name="boom", func=_boom),
}


def test_outcomes_arrive_one_at_a_time_in_config_order() -> None:
    measured: list[str] = []

    def spy(ctx: MetricContext) -> MetricResult:
        measured.append("ran")
        return MetricResult(value=len(ctx.files))

    types = {"spy": MetricType(name="spy", func=spy)}
    config = make_config(
        MetricSpec(name="first", type="spy"),
        MetricSpec(name="second", type="spy"),
        MetricSpec(name="third", type="spy"),
    )

    outcomes = iter_outcomes(config, PROJECT, metric_types=types)

    names = []
    for expected, outcome in enumerate(outcomes, start=1):
        names.append(outcome.spec.name)
        # each metric is measured as it is pulled, not all of them up front
        assert len(measured) == expected
    assert names == ["first", "second", "third"]


def test_nothing_is_measured_or_even_walked_until_the_first_pull() -> None:
    """The whole point: a caller can draw the run before it costs anything."""
    project = WatchfulProject({"a.py": "", "b.py": ""})
    config = make_config(MetricSpec(name="files", type="file_count"))

    outcomes = iter_outcomes(config, project, metric_types=METRIC_TYPES)

    assert project.walks == 0

    assert next(outcomes).spec.name == "files"
    assert project.walks == 1


def test_an_unknown_only_name_is_refused_at_the_call_not_at_the_first_pull() -> None:
    config = make_config(MetricSpec(name="files", type="file_count"))

    with pytest.raises(ConfigError) as excinfo:
        iter_outcomes(config, PROJECT, metric_types=METRIC_TYPES, only=["nope"])

    assert 'unknown metric "nope"' in excinfo.value.errors


def test_the_tree_is_walked_once_however_many_metrics_there_are() -> None:
    project = WatchfulProject({"a.py": "", "b.py": ""})
    config = make_config(
        MetricSpec(name="first", type="file_count"),
        MetricSpec(name="second", type="file_count"),
    )

    list(iter_outcomes(config, project, metric_types=METRIC_TYPES))

    assert project.walks == 1


def test_runs_metrics_and_reports_values() -> None:
    config = make_config(
        MetricSpec(name="files", type="file_count", ranges=("python",))
    )

    report = run(config, PROJECT, metric_types=METRIC_TYPES)

    outcome = report.outcomes[0]
    assert outcome.result is not None
    assert outcome.result.value == 2
    assert outcome.range_names == ("python",)
    assert outcome.error is None


def test_default_range_applies_when_none_given() -> None:
    config = make_config(MetricSpec(name="files", type="file_count"))

    report = run(config, PROJECT, metric_types=METRIC_TYPES)

    outcome = report.outcomes[0]
    assert outcome.result is not None
    assert outcome.result.value == 2
    assert outcome.range_names == ("python",)


def test_raising_metric_is_isolated() -> None:
    config = make_config(
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
    config = make_config(
        MetricSpec(name="files", type="file_count", ranges=("empty",)),
        extra_ranges={"empty": RangeSpec(name="empty", include=("nothing/**",))},
    )

    report = run(config, PROJECT, metric_types=METRIC_TYPES)

    outcome = report.outcomes[0]
    assert outcome.result is not None
    assert outcome.result.value == 0
    assert "ranges matched no files" in outcome.result.warnings


def test_only_filter_selects_metrics() -> None:
    config = make_config(
        MetricSpec(name="first", type="file_count"),
        MetricSpec(name="second", type="file_count"),
    )

    report = run(config, PROJECT, metric_types=METRIC_TYPES, only=["second"])

    assert [outcome.spec.name for outcome in report.outcomes] == ["second"]


def test_only_filter_rejects_unknown_names() -> None:
    config = make_config(MetricSpec(name="files", type="file_count"))

    with pytest.raises(ConfigError) as excinfo:
        run(config, PROJECT, metric_types=METRIC_TYPES, only=["nope"])

    assert 'unknown metric "nope"' in excinfo.value.errors


def test_outcome_carries_the_global_guide_when_the_metric_sets_none() -> None:
    config = make_config(
        MetricSpec(name="files", type="file_count"), display=DisplaySpec(guide=25)
    )

    report = run(config, PROJECT, metric_types=METRIC_TYPES)

    assert report.outcomes[0].guide == 25


def test_outcome_carries_the_metric_guide_over_the_global_one() -> None:
    config = make_config(
        MetricSpec(name="files", type="file_count", guide=5),
        display=DisplaySpec(guide=25),
    )

    report = run(config, PROJECT, metric_types=METRIC_TYPES)

    assert report.outcomes[0].guide == 5


def test_outcome_derives_its_guide_from_the_size_of_the_codebase() -> None:
    """With nothing pinned, debt is judged as a density: one unit per 100 lines."""
    project = FakeProject({"a.py": "x\n" * 250, "b.py": "y\n" * 50, "notes.md": ""})
    config = make_config(MetricSpec(name="files", type="file_count"))

    report = run(config, project, metric_types=METRIC_TYPES)

    # 300 lines of Python (notes.md is outside the default range) -> guide 3
    assert report.outcomes[0].guide == 3


def test_the_loc_range_overrides_which_files_are_counted() -> None:
    """400 lines in a.py, 100 in b.py: the default range would count all 500."""
    project = FakeProject({"a.py": "x\n" * 400, "b.py": "y\n" * 100})
    config = make_config(
        MetricSpec(name="files", type="file_count"),
        display=DisplaySpec(loc_range="just-a"),
        extra_ranges={"just-a": RangeSpec(name="just-a", include=("a.py",))},
    )

    report = run(config, project, metric_types=METRIC_TYPES)

    assert report.outcomes[0].guide == 4  # 400 lines, not 500


def test_an_empty_project_still_yields_a_guide() -> None:
    """Nothing to divide by is not an option: the guide is floored at 1."""
    config = make_config(MetricSpec(name="files", type="file_count"))

    report = run(config, FakeProject({"a.py": ""}), metric_types=METRIC_TYPES)

    assert report.outcomes[0].guide == 1


def test_a_failed_metric_still_carries_its_guide() -> None:
    """The error row is rendered like any other, so it needs a guide too."""
    config = make_config(
        MetricSpec(name="bad", type="boom", guide=7), display=DisplaySpec(guide=25)
    )

    report = run(config, PROJECT, metric_types=METRIC_TYPES)

    outcome = report.outcomes[0]
    assert outcome.error is not None
    assert outcome.guide == 7
