"""What a run says about itself while it is still running."""

from __future__ import annotations

from support import FakeProject, make_config

from tingle.mills import runner as runner_module
from tingle.mills.runner import run
from tingle.pacts.config import MetricSpec
from tingle.pacts.metrics import (
    MetricContext,
    MetricResult,
    MetricType,
    RunPhase,
    RunProgress,
)


def _file_count(ctx: MetricContext) -> MetricResult:
    return MetricResult(value=len(ctx.files))


COUNTER = {"counter": MetricType("counter", _file_count)}


def test_a_run_names_each_metric_before_it_measures_it() -> None:
    seen: list[RunProgress] = []
    config = make_config(
        MetricSpec(name="one", type="counter"),
        MetricSpec(name="two", type="counter"),
        MetricSpec(name="three", type="counter"),
    )

    run(config, FakeProject({"a.py": ""}), metric_types=COUNTER, progress=seen.append)

    measuring = [p for p in seen if p.phase is RunPhase.MEASURING]
    assert [(p.done, p.total, p.label) for p in measuring] == [
        (0, 3, "one"),
        (1, 3, "two"),
        (2, 3, "three"),
    ]


def test_the_count_is_of_metrics_finished_not_started() -> None:
    """`done` never reaches `total` while a metric is still running."""
    seen: list[RunProgress] = []
    config = make_config(MetricSpec(name="only", type="counter"))

    run(config, FakeProject({"a.py": ""}), metric_types=COUNTER, progress=seen.append)

    assert [p.done for p in seen if p.phase is RunPhase.MEASURING] == [0]


def test_scanning_reports_a_count_and_no_total() -> None:
    """A tree cannot say how big it is until it has been walked."""
    seen: list[RunProgress] = []
    every = runner_module.PROGRESS_EVERY
    project = FakeProject({f"f{index}.py": "" for index in range(every * 2)})

    run(make_config(), project, metric_types=COUNTER, progress=seen.append)

    scanning = [p for p in seen if p.phase is RunPhase.SCANNING]
    assert [(p.done, p.total) for p in scanning] == [(every, None), (every * 2, None)]


def test_a_walk_shorter_than_the_interval_says_nothing() -> None:
    seen: list[RunProgress] = []

    run(
        make_config(),
        FakeProject({"a.py": ""}),
        metric_types=COUNTER,
        progress=seen.append,
    )

    assert [p for p in seen if p.phase is RunPhase.SCANNING] == []


def test_a_run_with_no_sink_reports_the_same_thing() -> None:
    """The default is the same run, unwatched -- not a different one."""
    config = make_config(MetricSpec(name="one", type="counter"))
    project = FakeProject({"a.py": "", "b.py": "", "notes.md": ""})
    seen: list[RunProgress] = []

    watched = run(config, project, metric_types=COUNTER, progress=seen.append)
    unwatched = run(config, project, metric_types=COUNTER)

    assert seen
    assert watched == unwatched
