from __future__ import annotations

import asyncio
from pathlib import Path

from textual.widgets import Collapsible, Static

from tingle.gates.tui.app import MetricsApp
from tingle.pacts.config import MetricSpec
from tingle.pacts.diff import DiffOutcome, DiffReport, DiffResult
from tingle.pacts.metrics import MetricResult, Occurrence
from tingle.pacts.report import MetricOutcome, RunReport

RUN_REPORT = RunReport(
    root=Path("/proj"),
    source=Path("/proj/tingle.toml"),
    outcomes=(
        MetricOutcome(
            spec=MetricSpec(name="noqa-comments", type="regex_count"),
            range_names=("python",),
            result=MetricResult(
                value=2,
                occurrences=(
                    Occurrence(path="src/a.py", line=1),
                    Occurrence(path="src/b.py", line=9),
                ),
            ),
        ),
        MetricOutcome(
            spec=MetricSpec(name="python-files", type="file_count"),
            range_names=("python",),
            result=MetricResult(value=5),
        ),
    ),
)

DIFF_REPORT = DiffReport(
    root=Path("/proj"),
    source=Path("/proj/tingle.toml"),
    base_ref="main",
    merge_base="abc123",
    outcomes=(
        DiffOutcome(
            spec=MetricSpec(name="noqa-comments", type="regex_count"),
            range_names=("python",),
            result=DiffResult(
                net=1,
                added=2,
                removed=1,
                added_occurrences=(
                    Occurrence(path="src/a.py", line=3),
                    Occurrence(path="src/new.py", line=1),
                ),
                removed_occurrences=(Occurrence(path="src/b.py", line=9),),
            ),
            total=MetricResult(value=7),
        ),
    ),
)


def _grouped(name: str, group: str | None, value: int = 1) -> MetricOutcome:
    return MetricOutcome(
        spec=MetricSpec(name=name, type="file_count", group=group),
        range_names=(),
        result=MetricResult(
            value=value, occurrences=(Occurrence(path="x.py", line=1),)
        ),
    )


GROUPED_REPORT = RunReport(
    root=Path("/proj"),
    source=Path("/proj/tingle.toml"),
    outcomes=(
        _grouped("type-ignores", "typing"),
        _grouped("mypy-overrides", "typing"),
        _grouped("noqa-comments", "lint"),
        _grouped("python-files", None),
    ),
)


def _static_text(app: MetricsApp) -> str:
    return " ".join(str(node.render()) for node in app.query(Static))


def _groups(app: MetricsApp) -> list[Collapsible]:
    return [c for c in app.query(Collapsible) if "group" in c.classes]


def test_each_metric_is_a_collapsible_with_stats() -> None:
    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test():
            collapsibles = app.query(Collapsible)
            assert len(collapsibles) == 2
            titles = [node.title for node in collapsibles]
            assert any("noqa-comments" in title for title in titles)
            assert any("python-files" in title for title in titles)
            # the value stat rides along in the collapsed header
            assert any("2" in title for title in titles)

    asyncio.run(scenario())


def test_collapsibles_start_collapsed_and_expand_in_place() -> None:
    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test() as pilot:
            first = app.query_one("#metric-0", Collapsible)
            assert first.collapsed is True
            # the whole table stays on one screen; details are always in the DOM
            texts = _static_text(app)
            assert "src/a.py:1" in texts
            assert "src/b.py:9" in texts
            await pilot.click("#metric-0 CollapsibleTitle")
            assert first.collapsed is False
            # other metrics remain, so all stats stay visible
            assert app.query_one("#metric-1", Collapsible).collapsed is True

    asyncio.run(scenario())


def _focused_metric_id(app: MetricsApp) -> str | None:
    focused = app.focused
    if focused is None:
        return None
    collapsible = next(
        (a for a in focused.ancestors if isinstance(a, Collapsible)), None
    )
    return collapsible.id if collapsible else None


def test_arrows_move_between_metrics() -> None:
    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test() as pilot:
            assert _focused_metric_id(app) == "metric-0"
            await pilot.press("down")
            assert _focused_metric_id(app) == "metric-1"
            await pilot.press("up")
            assert _focused_metric_id(app) == "metric-0"

    asyncio.run(scenario())


def test_diff_report_stats_and_signed_occurrences() -> None:
    async def scenario() -> None:
        app = MetricsApp(DIFF_REPORT)
        async with app.run_test():
            title = app.query_one("#metric-0", Collapsible).title
            assert "+2" in title
            assert "-1" in title
            assert "net" in title
            texts = _static_text(app)
            assert "+ src/a.py:3" in texts
            assert "- src/b.py:9" in texts

    asyncio.run(scenario())


def test_grouped_report_nests_groups_and_metrics() -> None:
    async def scenario() -> None:
        app = MetricsApp(GROUPED_REPORT)
        async with app.run_test():
            groups = _groups(app)
            metrics = [c for c in app.query(Collapsible) if "metric" in c.classes]
            assert len(groups) == 3  # typing, lint, (ungrouped)
            assert len(metrics) == 4
            titles = [group.title for group in groups]
            assert "typing" in titles
            assert "lint" in titles
            assert "(ungrouped)" in titles
            # groups open at rest, metric file-results closed
            assert all(not group.collapsed for group in groups)
            assert all(metric.collapsed for metric in metrics)

    asyncio.run(scenario())


def test_expanding_metric_folds_other_groups_then_reopens() -> None:
    async def scenario() -> None:
        app = MetricsApp(GROUPED_REPORT)
        async with app.run_test() as pilot:
            typing = app.query_one("#group-0", Collapsible)
            lint = app.query_one("#group-1", Collapsible)
            ungrouped = app.query_one("#group-2", Collapsible)
            # expand a metric inside the typing group
            await pilot.click("#metric-0 CollapsibleTitle")
            assert typing.collapsed is False  # active group stays open
            assert lint.collapsed is True  # other groups fold away
            assert ungrouped.collapsed is True
            # collapsing it again returns to the all-open resting state
            await pilot.click("#metric-0 CollapsibleTitle")
            assert not any(
                group.collapsed for group in (typing, lint, ungrouped)
            )

    asyncio.run(scenario())


def test_quit_binding() -> None:
    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test() as pilot:
            await pilot.press("q")
        assert app.return_value is None

    asyncio.run(scenario())
