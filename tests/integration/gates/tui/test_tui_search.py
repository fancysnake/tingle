"""Search: what `/` matches, what a match reveals, and what escape restores."""

from __future__ import annotations

import asyncio

from tui_support import (
    BrowseTable,
    MetricsApp,
    MetricSpec,
    Occurrence,
    SearchBar,
    labels,
    outline,
    search_box,
    status,
    summed_report,
)

from tingle.pacts.metrics import MetricResult
from tingle.pacts.report import MetricOutcome

SEARCHABLE = summed_report(
    MetricOutcome(
        spec=MetricSpec(
            name="noqa-comments",
            type="regex_count",
            group="linting",
            description="lint escapes we carry",
        ),
        range_names=("python",),
        result=MetricResult(
            value=2,
            occurrences=(
                Occurrence(path="src/views.py", line=1),
                Occurrence(path="src/models.py", line=9),
            ),
        ),
    ),
    MetricOutcome(
        spec=MetricSpec(name="legacy-arch", type="symbol_uses", group="typing"),
        range_names=("python",),
        result=MetricResult(
            value=1, occurrences=(Occurrence(path="src/views.py", line=4),)
        ),
    ),
)


def test_slash_opens_the_search_box_and_puts_the_cursor_in_it() -> None:
    async def scenario() -> None:
        app = MetricsApp(SEARCHABLE)
        async with app.run_test() as pilot:
            assert search_box(app).has_class("hidden")

            await pilot.press("/")

            assert not search_box(app).has_class("hidden")
            assert isinstance(app.focused, SearchBar)

    asyncio.run(scenario())


def test_every_bare_letter_the_app_binds_reaches_the_search_box_as_text() -> None:
    """The whole binding risk in one test: f folds, q quits, 0 and V sort."""

    async def scenario() -> None:
        app = MetricsApp(SEARCHABLE)
        async with app.run_test() as pilot:
            await pilot.press("/")

            await pilot.press("f", "q", "0", "V", "g", "n", "t", "c", "j", "k")

            assert search_box(app).value == "fq0Vgntcjk"
            assert app.is_running  # q did not quit
            assert status(app).startswith("search:")  # 0 and V did not sort

    asyncio.run(scenario())


def test_a_file_query_opens_a_fully_folded_tree_onto_that_file_alone() -> None:
    async def scenario() -> None:
        app = MetricsApp(SEARCHABLE)
        async with app.run_test() as pilot:
            await pilot.press("f")
            assert labels(app) == ["linting", "typing"]

            await pilot.press("/")
            await pilot.press(*"models.py")

            # one keystroke from a shut tree to the one file that matched
            assert labels(app) == [
                "linting",
                "noqa-comments",
                "lint escapes we carry",
                "ranges: python",
                "src/models.py:9",
            ]

    asyncio.run(scenario())


def test_escape_leaves_search_mode_and_restores_the_outline_untouched() -> None:
    async def scenario() -> None:
        app = MetricsApp(SEARCHABLE)
        async with app.run_test() as pilot:
            await pilot.press("f")
            before = outline(app)

            await pilot.press("/")
            await pilot.press(*"views.py")
            assert labels(app) != ["linting", "typing"]

            await pilot.press("escape")

            assert outline(app) == before
            assert search_box(app).value == ""
            assert search_box(app).has_class("hidden")
            assert isinstance(app.focused, BrowseTable)

    asyncio.run(scenario())


def test_a_name_match_leaves_the_metric_as_the_reader_had_it() -> None:
    async def scenario() -> None:
        app = MetricsApp(SEARCHABLE)
        async with app.run_test() as pilot:
            await pilot.press("/")
            await pilot.press(*"legacy")

            # matched on the row's own text, so nothing underneath is singled out
            assert labels(app) == ["typing", "legacy-arch"]

    asyncio.run(scenario())


def test_a_description_match_opens_the_metric_on_the_words_that_matched() -> None:
    async def scenario() -> None:
        app = MetricsApp(SEARCHABLE)
        async with app.run_test() as pilot:
            await pilot.press("/")
            await pilot.press(*"escapes")

            # the matching words are in a detail row, so the row is shown
            assert labels(app) == [
                "linting",
                "noqa-comments",
                "lint escapes we carry",
                "ranges: python",
                "src/views.py:1",
                "src/models.py:9",
            ]

    asyncio.run(scenario())


def test_search_is_case_sensitive_and_empties_the_view_when_nothing_matches() -> None:
    async def scenario() -> None:
        app = MetricsApp(SEARCHABLE)
        async with app.run_test() as pilot:
            await pilot.press("/")
            await pilot.press(*"Legacy")

            assert labels(app) == []
            assert status(app) == "search: 'Legacy' — 0 metrics — esc to leave"

    asyncio.run(scenario())


def test_a_group_with_no_matching_metric_disappears() -> None:
    async def scenario() -> None:
        app = MetricsApp(SEARCHABLE)
        async with app.run_test() as pilot:
            await pilot.press("/")
            await pilot.press(*"models.py")

            assert "typing" not in labels(app)

    asyncio.run(scenario())


def test_a_fold_made_during_a_search_beats_the_reveal_and_dies_with_it() -> None:
    async def scenario() -> None:
        app = MetricsApp(SEARCHABLE)
        async with app.run_test() as pilot:
            await pilot.press("/")
            await pilot.press(*"views.py")
            assert "src/views.py:1" in labels(app)

            await pilot.press("enter")  # hand the rows back, keeping the query
            await pilot.press("down", "left")  # fold the revealed metric

            assert "src/views.py:1" not in labels(app)

            await pilot.press("escape")

            # the gesture went with the query; the reader's outline is intact
            assert labels(app)[:2] == ["linting", "noqa-comments"]

    asyncio.run(scenario())


def test_enter_hands_the_rows_back_without_giving_up_the_query() -> None:
    async def scenario() -> None:
        app = MetricsApp(SEARCHABLE)
        async with app.run_test() as pilot:
            await pilot.press("/")
            await pilot.press(*"legacy")

            await pilot.press("enter")

            assert isinstance(app.focused, BrowseTable)
            assert labels(app) == ["typing", "legacy-arch"]

    asyncio.run(scenario())


def test_the_status_line_counts_what_the_query_found() -> None:
    async def scenario() -> None:
        app = MetricsApp(SEARCHABLE)
        async with app.run_test() as pilot:
            await pilot.press("/")
            await pilot.press(*"views.py")
            assert status(app) == "search: 'views.py' — 2 metrics — esc to leave"

            await pilot.press(*"1")  # no such path
            assert status(app) == "search: 'views.py1' — 0 metrics — esc to leave"

    asyncio.run(scenario())
