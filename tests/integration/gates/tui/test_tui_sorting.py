"""Sorting the table: the ten keys, the stack, and what a flat sort costs."""

from __future__ import annotations

import asyncio

from tui_support import (
    GROUPED_REPORT,
    RUN_REPORT,
    MetricsApp,
    MetricSpec,
    column,
    headers,
    labels,
    outline,
    status,
    summed_report,
)

from tingle.pacts.metrics import MetricResult
from tingle.pacts.report import MetricOutcome


def _sortable(
    name: str, kind: str, *, group: str, value: int, guide: int = 100
) -> MetricOutcome:
    return MetricOutcome(
        spec=MetricSpec(name=name, type=kind, group=group),
        range_names=(),
        result=MetricResult(value=value),
        guide=guide,
    )


#: Deliberately disagreeing orders: config, name, type, value and score each
#: rank these three differently, so a test can tell which one is in charge.
#: `mid` is the worst by score (20 of 20) and the middle one by value.
SORTABLE = summed_report(
    _sortable("zeta", "regex_count", group="typing", value=5),
    _sortable("alpha", "file_count", group="typing", value=90),
    _sortable("mid", "regex_count", group="lint", value=20, guide=20),
)


def test_sorting_by_name_flattens_the_view_and_orders_every_metric() -> None:
    async def scenario() -> None:
        app = MetricsApp(SORTABLE)
        async with app.run_test() as pilot:
            await pilot.press("n")

            assert labels(app) == ["alpha", "mid", "zeta"]

    asyncio.run(scenario())


def test_sorting_by_name_then_type_gives_type_major_order() -> None:
    async def scenario() -> None:
        app = MetricsApp(SORTABLE)
        async with app.run_test() as pilot:
            await pilot.press("n", "t")

            assert labels(app) == ["alpha", "mid", "zeta"]  # file_count, then regex
            assert column(app, 1) == ["file_count", "regex_count", "regex_count"]

    asyncio.run(scenario())


def test_a_lowercase_key_sorts_up_and_its_shifted_twin_sorts_down() -> None:
    async def scenario() -> None:
        app = MetricsApp(SORTABLE)
        async with app.run_test() as pilot:
            await pilot.press("v")
            assert column(app, 2) == ["🚧 5", "🚨 20", "🚨 90"]

            await pilot.press("V")
            assert column(app, 2) == ["🚨 90", "🚨 20", "🚧 5"]

    asyncio.run(scenario())


def test_sorting_by_score_ranks_against_each_metrics_own_guide() -> None:
    async def scenario() -> None:
        app = MetricsApp(SORTABLE)
        async with app.run_test() as pilot:
            # mid is 20 against a guide of 20, so it is worse than alpha's
            # 90 against 100 even though it is the smaller number
            await pilot.press("C")

            assert labels(app) == ["mid", "alpha", "zeta"]

    asyncio.run(scenario())


def test_the_sorted_columns_header_says_which_way_it_is_running() -> None:
    async def scenario() -> None:
        app = MetricsApp(SORTABLE)
        async with app.run_test() as pilot:
            assert headers(app) == ["Group / Metric", "Type", "Value"]

            await pilot.press("v")
            assert headers(app) == ["Group / Metric", "Type", "Value ▲"]

            await pilot.press("V")
            assert headers(app) == ["Group / Metric", "Type", "Value ▼"]

            await pilot.press("n")
            assert headers(app) == ["Group / Metric ▲", "Type", "Value"]

            await pilot.press("0")
            assert headers(app) == ["Group / Metric", "Type", "Value"]

    asyncio.run(scenario())


def test_sorting_by_group_keeps_the_outline_and_orders_groups_by_name() -> None:
    async def scenario() -> None:
        app = MetricsApp(SORTABLE)
        async with app.run_test() as pilot:
            await pilot.press("g")

            # no occurrences and no ranges, so no metric here is foldable
            assert outline(app) == [
                "▾ lint",
                "    mid",
                "▾ typing",
                "    alpha",
                "    zeta",
            ]

            await pilot.press("G")

            assert labels(app)[0] == "typing"  # turned over, outline intact

    asyncio.run(scenario())


def test_zero_restores_config_order_the_outline_and_the_fold_state() -> None:
    async def scenario() -> None:
        app = MetricsApp(GROUPED_REPORT)
        async with app.run_test() as pilot:
            await pilot.press("left")  # fold the first group
            assert labels(app) == [
                "typing",
                "lint",
                "noqa-comments",
                "(ungrouped)",
                "python-files",
            ]

            await pilot.press("n")
            assert labels(app) == [
                "mypy-overrides",
                "noqa-comments",
                "python-files",
                "type-ignores",
            ]

            await pilot.press("0")

            # config order is back, and so is the fold the sort hid
            assert labels(app)[:2] == ["typing", "lint"]

    asyncio.run(scenario())


def test_a_flat_sort_puts_occurrences_out_of_reach_until_the_sort_is_cleared() -> None:
    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test() as pilot:
            await pilot.press("right")
            assert "src/a.py:1" in labels(app)

            await pilot.press("n")
            assert outline(app) == ["  noqa-comments", "  python-files"]
            await pilot.press("right")  # nothing to unfold while flat
            assert "src/a.py:1" not in labels(app)

            await pilot.press("0")

            assert "src/a.py:1" in labels(app)

    asyncio.run(scenario())


def test_the_sort_bar_says_what_is_deciding_the_order() -> None:
    async def scenario() -> None:
        app = MetricsApp(SORTABLE)
        async with app.run_test() as pilot:
            assert status(app) == "sort: config order"

            await pilot.press("g")
            assert status(app) == "sort: group asc"

            await pilot.press("N")
            assert status(app) == (
                "sort: name desc then group asc  ·  flat, no folding — 0 to reset"
            )

            await pilot.press("0")
            assert status(app) == "sort: config order"

    asyncio.run(scenario())


def test_pushing_a_key_already_in_the_stack_moves_it_to_the_front() -> None:
    async def scenario() -> None:
        app = MetricsApp(SORTABLE)
        async with app.run_test() as pilot:
            await pilot.press("n", "t", "n")

            assert status(app).startswith("sort: name asc then type asc")

    asyncio.run(scenario())


def test_asking_for_a_stacked_key_the_other_way_turns_it_over_in_place() -> None:
    async def scenario() -> None:
        app = MetricsApp(SORTABLE)
        async with app.run_test() as pilot:
            await pilot.press("t", "v")
            assert status(app).startswith("sort: value asc then type asc")

            await pilot.press("V")

            # the stack is the same depth: value turned over, not stacked twice
            assert status(app).startswith("sort: value desc then type asc")

    asyncio.run(scenario())
