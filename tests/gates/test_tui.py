from __future__ import annotations

import asyncio
from pathlib import Path

from textual.widgets import DataTable

from tingle.gates.tui.app import DetailScreen, MetricsApp
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


def test_main_table_lists_metrics() -> None:
    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test():
            table = app.query_one(DataTable)
            assert table.row_count == 2
            first_row = table.get_row_at(0)
            assert first_row[0].plain == "noqa-comments"
            assert first_row[3].plain == "2"

    asyncio.run(scenario())


def test_enter_opens_detail_and_escape_returns() -> None:
    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test() as pilot:
            await pilot.press("enter")
            assert isinstance(app.screen, DetailScreen)
            rendered = app.screen.query("Static")
            texts = " ".join(str(node.render()) for node in rendered)
            assert "src/a.py:1" in texts
            assert "src/b.py:9" in texts
            await pilot.press("escape")
            assert not isinstance(app.screen, DetailScreen)

    asyncio.run(scenario())


def test_sorting_by_value_column_and_toggle() -> None:
    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test() as pilot:
            table = app.query_one(DataTable)
            await pilot.press("4")  # sort by Value ascending
            assert table.get_row_at(0)[3].plain == "2"
            await pilot.press("4")  # same key flips direction
            assert table.get_row_at(0)[3].plain == "5"

    asyncio.run(scenario())


def test_diff_report_columns_and_detail() -> None:
    async def scenario() -> None:
        app = MetricsApp(DIFF_REPORT)
        async with app.run_test() as pilot:
            table = app.query_one(DataTable)
            assert table.row_count == 1
            row = table.get_row_at(0)
            assert row[2].plain == "+2"
            assert row[3].plain == "-1"
            assert row[4].plain == "+1"
            assert row[5].plain == "7"
            await pilot.press("enter")
            assert isinstance(app.screen, DetailScreen)
            texts = " ".join(
                str(node.render()) for node in app.screen.query("Static")
            )
            assert "+ src/a.py:3" in texts
            assert "- src/b.py:9" in texts

    asyncio.run(scenario())


def test_quit_binding() -> None:
    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test() as pilot:
            await pilot.press("q")
        assert app.return_value is None

    asyncio.run(scenario())
