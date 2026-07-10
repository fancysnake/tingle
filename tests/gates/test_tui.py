from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from textual.binding import Binding
from textual.command import CommandList, CommandPalette
from textual.containers import VerticalScroll
from textual.widgets import Collapsible, Input, Static

if TYPE_CHECKING:
    from textual.pilot import Pilot

from tingle.gates.tui.app import MetricsApp, NavCollapsible
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


def test_arrows_navigate_even_when_content_overflows() -> None:
    # the enclosing VerticalScroll binds the arrows for scrolling; ours sit
    # on NavCollapsible, below it in the bubbling chain, so they win
    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test(size=(80, 6)) as pilot:
            scroll = app.query_one(VerticalScroll)
            await pilot.press("right")  # unfold, making the content overflow
            await pilot.pause()
            assert scroll.max_scroll_y > 0  # the view really is too tall
            await pilot.press("down")
            assert _focused_metric_id(app) == "metric-1"

    asyncio.run(scenario())


def test_jk_still_work_as_hidden_aliases() -> None:
    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test() as pilot:
            await pilot.press("j")
            assert _focused_metric_id(app) == "metric-1"
            await pilot.press("k")
            assert _focused_metric_id(app) == "metric-0"

    asyncio.run(scenario())


def test_space_toggles_focused_header() -> None:
    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test() as pilot:
            first = app.query_one("#metric-0", Collapsible)
            assert first.collapsed is True
            await pilot.press("space")
            assert first.collapsed is False
            await pilot.press("space")
            assert first.collapsed is True

    asyncio.run(scenario())


def test_f_folds_and_unfolds_every_group() -> None:
    async def scenario() -> None:
        app = MetricsApp(GROUPED_REPORT)
        async with app.run_test() as pilot:
            groups = _groups(app)
            assert all(not group.collapsed for group in groups)  # open at rest
            await pilot.press("f")
            assert all(group.collapsed for group in groups)
            await pilot.press("f")
            assert all(not group.collapsed for group in groups)

    asyncio.run(scenario())


def test_f_folds_all_when_only_some_groups_are_open() -> None:
    # a mixed state folds rather than toggling each header independently
    async def scenario() -> None:
        app = MetricsApp(GROUPED_REPORT)
        async with app.run_test() as pilot:
            app.query_one("#group-0", Collapsible).collapsed = True
            await pilot.pause()
            await pilot.press("f")
            assert all(group.collapsed for group in _groups(app))

    asyncio.run(scenario())


def test_f_leaves_metric_file_results_untouched() -> None:
    async def scenario() -> None:
        app = MetricsApp(GROUPED_REPORT)
        async with app.run_test() as pilot:
            metric = app.query_one("#metric-0", Collapsible)
            metric.collapsed = False  # its file results are showing
            await pilot.pause()
            await pilot.press("f")  # folds the groups...
            assert all(group.collapsed for group in _groups(app))
            assert metric.collapsed is False  # ...but not the files
            await pilot.press("f")
            assert metric.collapsed is False

    asyncio.run(scenario())


def test_f_folds_metrics_when_the_report_has_no_groups() -> None:
    # a flat accordion has no group headers, so metrics are the top level
    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test() as pilot:
            assert _groups(app) == []
            metrics = [c for c in app.query(Collapsible) if "metric" in c.classes]
            assert all(metric.collapsed for metric in metrics)
            await pilot.press("f")
            assert all(not metric.collapsed for metric in metrics)
            await pilot.press("f")
            assert all(metric.collapsed for metric in metrics)

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


def test_groups_and_metrics_fold_independently() -> None:
    async def scenario() -> None:
        app = MetricsApp(GROUPED_REPORT)
        async with app.run_test() as pilot:
            typing = app.query_one("#group-0", Collapsible)
            lint = app.query_one("#group-1", Collapsible)
            # expanding a metric leaves the other groups untouched
            await pilot.click("#metric-0 CollapsibleTitle")
            assert app.query_one("#metric-0", Collapsible).collapsed is False
            assert typing.collapsed is False
            assert lint.collapsed is False  # not folded away
            # groups fold on their own without disturbing metrics
            await pilot.click("#group-1 CollapsibleTitle")
            assert lint.collapsed is True
            assert app.query_one("#metric-0", Collapsible).collapsed is False

    asyncio.run(scenario())


def test_right_unfolds_and_left_folds_focused_header() -> None:
    async def scenario() -> None:
        app = MetricsApp(GROUPED_REPORT)
        async with app.run_test() as pilot:
            # focus starts on the first group header (expanded at rest)
            typing = app.query_one("#group-0", Collapsible)
            await pilot.press("left")  # fold the group
            assert typing.collapsed is True
            await pilot.press("right")  # unfold it again
            assert typing.collapsed is False
            # move down to a metric header and unfold its file results
            await pilot.press("down")
            await pilot.press("right")
            assert app.query_one("#metric-0", Collapsible).collapsed is False
            await pilot.press("left")
            assert app.query_one("#metric-0", Collapsible).collapsed is True

    asyncio.run(scenario())


def test_hl_still_fold_and_unfold_as_hidden_aliases() -> None:
    async def scenario() -> None:
        app = MetricsApp(GROUPED_REPORT)
        async with app.run_test() as pilot:
            typing = app.query_one("#group-0", Collapsible)
            await pilot.press("h")
            assert typing.collapsed is True
            await pilot.press("l")
            assert typing.collapsed is False

    asyncio.run(scenario())


def _active_keys(app: MetricsApp) -> set[str]:
    return {active.binding.key for active in app.active_bindings.values()}


def test_f_keeps_the_arrows_alive_when_folding_from_inside_a_group() -> None:
    # regression: `down` focuses a metric title nested in a group, and `f`
    # then hid it, so textual dropped focus. The arrows are bound on
    # NavCollapsible, so an unfocused app has none left to refocus with --
    # pressing `f` again unfolded the groups but never revived them.
    async def scenario() -> None:
        app = MetricsApp(GROUPED_REPORT)
        async with app.run_test() as pilot:
            await pilot.press("down")  # into the first group's metric rows
            await pilot.press("f")
            await pilot.pause()
            assert app.focused is not None
            assert {"up", "down"} <= _active_keys(app)

            await pilot.press("f")  # unfold again
            await pilot.pause()
            assert {"up", "down"} <= _active_keys(app)

            before = app.focused
            await pilot.press("down")
            await pilot.pause()
            assert app.focused is not before  # and they still move focus

    asyncio.run(scenario())


def test_f_parks_focus_on_the_enclosing_group() -> None:
    # folding must not fling the cursor back to the top of the listing
    async def scenario() -> None:
        app = MetricsApp(GROUPED_REPORT)
        async with app.run_test() as pilot:
            for _ in range(4):  # typing, its 2 metrics, then into lint
                await pilot.press("down")
            await pilot.pause()
            await pilot.press("f")
            await pilot.pause()
            assert app.focused is not None
            assert app.focused.parent is _groups(app)[1]  # lint, not typing

    asyncio.run(scenario())


def test_wasd_is_no_longer_bound() -> None:
    # wasd only ever existed because the arrows were unavailable
    bindings = (*MetricsApp.BINDINGS, *NavCollapsible.BINDINGS)
    keys = {b.key for b in bindings if isinstance(b, Binding)}
    assert keys.isdisjoint({"w", "a", "s", "d"})


def test_arrows_are_the_advertised_navigation_keys() -> None:
    # ctrl+p is taken by the VS Code terminal, so the palette moves to "p"
    assert MetricsApp.ENABLE_COMMAND_PALETTE is True
    assert MetricsApp.COMMAND_PALETTE_BINDING == "p"
    # navigation must NOT be app-level: an app arrow binding would need
    # priority=True to beat VerticalScroll, and that steals the palette's
    app_bindings = [b for b in MetricsApp.BINDINGS if isinstance(b, Binding)]
    nav_bindings = [b for b in NavCollapsible.BINDINGS if isinstance(b, Binding)]
    assert {b.key for b in app_bindings}.isdisjoint({"up", "down", "left", "right"})
    assert not any(b.priority for b in (*app_bindings, *nav_bindings))
    shown = {b.key: b.description for b in nav_bindings if b.show}
    assert shown == {
        "up": "Prev",
        "down": "Next",
        "left": "Fold",
        "right": "Unfold",
    }
    assert all(not b.show for b in nav_bindings if b.key in {"h", "j", "k", "l"})


def test_pressing_p_opens_the_command_palette() -> None:
    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test() as pilot:
            await pilot.press("p")
            assert isinstance(app.screen, CommandPalette)

    asyncio.run(scenario())


async def _palette_options(pilot: Pilot[None], query: str) -> CommandList:
    """Open the palette, search, and wait for its result list to fill."""
    await pilot.press("p")
    assert isinstance(pilot.app.screen, CommandPalette)
    await pilot.press(*query)
    command_list = pilot.app.screen.query_one(CommandList)
    for _ in range(50):  # the palette searches on a worker
        await pilot.pause()
        if command_list.option_count >= 2:
            return command_list
    msg = f"palette found {command_list.option_count} options for {query!r}"
    raise AssertionError(msg)


def test_open_palette_keeps_the_arrow_keys() -> None:
    # regression: arrows used to be app-level priority bindings. Priority
    # bindings are checked app-down even while a modal screen is up, so
    # `down` ran focus_metric against the palette screen -- which has no
    # CollapsibleTitle, so it did nothing, yet still reported the key as
    # handled. The palette's own result list never saw the arrows.
    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test() as pilot:
            command_list = await _palette_options(pilot, "t")
            assert command_list.highlighted == 0
            await pilot.press("down")
            await pilot.pause()
            assert command_list.highlighted == 1
            await pilot.press("up")
            await pilot.pause()
            assert command_list.highlighted == 0
            assert isinstance(app.screen, CommandPalette)  # still open

    asyncio.run(scenario())


def test_letter_bindings_do_not_eat_the_palette_search_box() -> None:
    # "p" is a priority binding, "q" quits and "f" folds; inside the
    # palette all three must reach its Input as plain text
    async def scenario() -> None:
        app = MetricsApp(GROUPED_REPORT)
        async with app.run_test() as pilot:
            await pilot.press("p")
            assert isinstance(app.screen, CommandPalette)
            await pilot.press("f", "q", "u", "i", "p")
            await pilot.pause()
            assert app.screen.query_one(Input).value == "fquip"
            assert app.is_running  # "q" did not quit
            assert all(not group.collapsed for group in _groups(app))  # "f" no-op

    asyncio.run(scenario())


def test_quit_binding() -> None:
    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test() as pilot:
            await pilot.press("q")
        assert app.return_value is None

    asyncio.run(scenario())
