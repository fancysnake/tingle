"""The TUI as a table: what it draws, and what the keys do to it.

Rewritten for the `DataTable` that replaced the `Collapsible` accordion.
Every behaviour the accordion tests pinned down is still asserted here --
navigation, folding, fold-all, descriptions, opening a hit, the palette
and the binding rules -- against the table instead of the widget tree.

Three of the old tests are gone rather than rewritten, and this is the
call-out the plan asked for:

- `test_clicking_empty_space_does_not_steal_focus_from_the_rows` and
  `test_the_view_still_scrolls_when_the_content_overflows` both guarded
  the `VerticalScroll` the accordion sat in. The table scrolls itself and
  is the only focusable thing on the screen, so neither failure mode
  exists any more.
- `test_a_metric_description_stays_visible_when_folded` asserted the
  opposite of what a table can do. A description is a row now, so folding
  a metric hides it along with the metric's hits; that is the agreed cost
  of giving descriptions somewhere to live. The new
  `test_a_folded_metric_hides_what_it_says_about_itself` pins the new rule
  so the change cannot happen twice by accident.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from textual.binding import Binding
from textual.command import CommandList, CommandPalette
from textual.widgets import Input

from tingle.gates.tui.app import BrowseTable, MetricsApp
from tingle.links.editor import VsCodeCli
from tingle.pacts.config import MetricSpec
from tingle.pacts.diff import DiffOutcome, DiffReport, DiffResult
from tingle.pacts.metrics import MetricResult, Occurrence
from tingle.pacts.report import MetricOutcome, RunReport

if TYPE_CHECKING:
    from textual.pilot import Pilot

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


def _grouped(name: str, group: str | None, *, value: int = 1) -> MetricOutcome:
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


def _summed_report(*outcomes: MetricOutcome) -> RunReport:
    return RunReport(
        root=Path("/proj"), source=Path("/proj/tingle.toml"), outcomes=outcomes
    )


def _valued(name: str, group: str, *, value: int, guide: int = 100) -> MetricOutcome:
    return MetricOutcome(
        spec=MetricSpec(name=name, type="file_count", group=group),
        range_names=(),
        result=MetricResult(value=value),
        guide=guide,
    )


def _column(app: MetricsApp, index: int) -> list[str]:
    """One column of the table exactly as it is drawn."""
    table = app.query_one(BrowseTable)
    return [str(table.get_row_at(row)[index]) for row in range(table.row_count)]


def _outline(app: MetricsApp) -> list[str]:
    """Return the first column: indentation, fold marker and label, verbatim."""
    return _column(app, 0)


def _labels(app: MetricsApp) -> list[str]:
    """Just the labels, with the outline's indent and marker stripped off."""
    return [text.strip().lstrip("▾▸ ").strip() for text in _outline(app)]


def _cursor(app: MetricsApp) -> str:
    """Return the label of the row the cursor is on."""
    return _labels(app)[app.query_one(BrowseTable).cursor_row]


def _recording_opener(*, available: bool = True) -> tuple[VsCodeCli, list[list[str]]]:
    """Build the real VS Code adapter with its `code` spawn captured, not run."""
    calls: list[list[str]] = []
    opener = VsCodeCli(
        environ={"TERM_PROGRAM": "vscode"} if available else {},
        which=lambda name: "/usr/bin/code" if name == "code" else None,
        spawn=lambda args: calls.append(list(args)),
    )
    return opener, calls


def test_the_table_has_a_row_per_metric_with_its_type_and_value() -> None:
    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test():
            assert _labels(app) == ["noqa-comments", "python-files"]
            assert _column(app, 1) == ["regex_count", "file_count"]
            assert _column(app, 2) == ["🦠 2", "🚧 5"]

    asyncio.run(scenario())


def test_metrics_start_folded_and_unfold_in_place() -> None:
    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test() as pilot:
            assert _outline(app) == ["▸ noqa-comments", "▸ python-files"]

            await pilot.press("right")

            assert _labels(app) == [
                "noqa-comments",
                "ranges: python",
                "src/a.py:1",
                "src/b.py:9",
                "python-files",
            ]

    asyncio.run(scenario())


def test_a_metric_says_what_it_measures_above_what_it_found() -> None:
    async def scenario() -> None:
        report = _summed_report(
            MetricOutcome(
                spec=MetricSpec(
                    name="noqa-comments",
                    type="regex_count",
                    description="how many lint escapes we carry",
                ),
                range_names=("python",),
                result=MetricResult(
                    value=1, occurrences=(Occurrence(path="src/a.py", line=1),)
                ),
            )
        )
        app = MetricsApp(report)
        async with app.run_test() as pilot:
            await pilot.press("right")

            assert _labels(app) == [
                "noqa-comments",
                "how many lint escapes we carry",
                "ranges: python",
                "src/a.py:1",
            ]

    asyncio.run(scenario())


def test_a_folded_metric_hides_what_it_says_about_itself() -> None:
    """The agreed cost of making the description a row: folding hides it."""

    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test() as pilot:
            await pilot.press("right")
            assert "ranges: python" in _labels(app)

            await pilot.press("left")

            assert _labels(app) == ["noqa-comments", "python-files"]

    asyncio.run(scenario())


def test_a_failed_metric_shows_the_error_where_it_can_be_read() -> None:
    async def scenario() -> None:
        report = _summed_report(
            MetricOutcome(
                spec=MetricSpec(name="broken", type="file_count"),
                range_names=("python",),
                error="ValueError: boom",
            )
        )
        app = MetricsApp(report)
        async with app.run_test() as pilot:
            assert _column(app, 2) == ["ERROR"]

            await pilot.press("right")

            assert "ValueError: boom" in _labels(app)

    asyncio.run(scenario())


def test_arrows_move_between_rows() -> None:
    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test() as pilot:
            assert _cursor(app) == "noqa-comments"

            await pilot.press("down")
            assert _cursor(app) == "python-files"

            await pilot.press("up")
            assert _cursor(app) == "noqa-comments"

    asyncio.run(scenario())


def test_jk_still_work_as_hidden_aliases() -> None:
    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test() as pilot:
            await pilot.press("j")
            assert _cursor(app) == "python-files"

            await pilot.press("k")
            assert _cursor(app) == "noqa-comments"

    asyncio.run(scenario())


def test_right_unfolds_and_left_folds_the_row_under_the_cursor() -> None:
    async def scenario() -> None:
        app = MetricsApp(GROUPED_REPORT)
        async with app.run_test() as pilot:
            assert _cursor(app) == "typing"

            await pilot.press("left")
            assert _outline(app)[0] == "▸ typing"
            assert "type-ignores" not in _labels(app)

            await pilot.press("right")
            assert _outline(app)[0] == "▾ typing"
            assert "type-ignores" in _labels(app)

    asyncio.run(scenario())


def test_hl_still_fold_and_unfold_as_hidden_aliases() -> None:
    async def scenario() -> None:
        app = MetricsApp(GROUPED_REPORT)
        async with app.run_test() as pilot:
            await pilot.press("h")
            assert _outline(app)[0] == "▸ typing"

            await pilot.press("l")
            assert _outline(app)[0] == "▾ typing"

    asyncio.run(scenario())


def test_folding_from_a_hit_folds_the_metric_and_lands_the_cursor_on_it() -> None:
    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test() as pilot:
            await pilot.press("right", "down", "down")
            assert _cursor(app) == "src/a.py:1"

            await pilot.press("left")

            assert _cursor(app) == "noqa-comments"
            assert _labels(app) == ["noqa-comments", "python-files"]

    asyncio.run(scenario())


def test_space_toggles_the_row_under_the_cursor() -> None:
    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test() as pilot:
            await pilot.press("space")
            assert "ranges: python" in _labels(app)

            await pilot.press("space")
            assert _labels(app) == ["noqa-comments", "python-files"]

    asyncio.run(scenario())


def test_groups_and_metrics_fold_independently() -> None:
    async def scenario() -> None:
        app = MetricsApp(GROUPED_REPORT)
        async with app.run_test() as pilot:
            await pilot.press("down", "space")  # unfold type-ignores
            assert _labels(app)[:3] == ["typing", "type-ignores", "x.py:1"]

            await pilot.press("up", "space")  # fold the group around it
            assert _labels(app)[:2] == ["typing", "lint"]

    asyncio.run(scenario())


def test_a_grouped_report_nests_metrics_under_their_group() -> None:
    async def scenario() -> None:
        app = MetricsApp(GROUPED_REPORT)
        async with app.run_test():
            assert _outline(app) == [
                "▾ typing",
                "  ▸ type-ignores",
                "  ▸ mypy-overrides",
                "▾ lint",
                "  ▸ noqa-comments",
                "▾ (ungrouped)",
                "  ▸ python-files",
            ]

    asyncio.run(scenario())


def test_space_on_an_occurrence_opens_it_at_its_line() -> None:
    async def scenario() -> None:
        opener, calls = _recording_opener()
        app = MetricsApp(RUN_REPORT, opener)
        async with app.run_test() as pilot:
            await pilot.press("right", "down", "down")
            assert _cursor(app) == "src/a.py:1"

            await pilot.press("space")

            # the path is resolved under the report root, at the hit's line
            assert calls == [["/usr/bin/code", "--goto", f"{Path('/proj/src/a.py')}:1"]]

    asyncio.run(scenario())


def test_a_diff_occurrence_opens_too() -> None:
    async def scenario() -> None:
        opener, calls = _recording_opener()
        app = MetricsApp(DIFF_REPORT, opener)
        async with app.run_test() as pilot:
            await pilot.press("right", "down", "down")

            await pilot.press("space")

            assert calls == [["/usr/bin/code", "--goto", f"{Path('/proj/src/a.py')}:3"]]

    asyncio.run(scenario())


def test_space_does_not_open_when_no_editor_is_reachable() -> None:
    async def scenario() -> None:
        opener, calls = _recording_opener(available=False)
        app = MetricsApp(RUN_REPORT, opener)
        async with app.run_test() as pilot:
            await pilot.press("right", "down", "down")

            await pilot.press("space")

            assert not calls

    asyncio.run(scenario())


def test_space_on_a_metric_toggles_rather_than_opening() -> None:
    async def scenario() -> None:
        opener, calls = _recording_opener()
        app = MetricsApp(RUN_REPORT, opener)
        async with app.run_test() as pilot:
            await pilot.press("space")

            assert not calls
            assert "ranges: python" in _labels(app)

    asyncio.run(scenario())


def test_f_folds_and_unfolds_every_group() -> None:
    async def scenario() -> None:
        app = MetricsApp(GROUPED_REPORT)
        async with app.run_test() as pilot:
            await pilot.press("f")
            assert _labels(app) == ["typing", "lint", "(ungrouped)"]

            await pilot.press("f")
            assert _labels(app) == [
                "typing",
                "type-ignores",
                "mypy-overrides",
                "lint",
                "noqa-comments",
                "(ungrouped)",
                "python-files",
            ]

    asyncio.run(scenario())


def test_f_folds_all_when_only_some_groups_are_open() -> None:
    async def scenario() -> None:
        app = MetricsApp(GROUPED_REPORT)
        async with app.run_test() as pilot:
            await pilot.press("left")  # fold just the first group
            assert _labels(app)[:2] == ["typing", "lint"]

            await pilot.press("f")

            assert _labels(app) == ["typing", "lint", "(ungrouped)"]

    asyncio.run(scenario())


def test_f_leaves_a_metrics_own_fold_state_untouched() -> None:
    async def scenario() -> None:
        app = MetricsApp(GROUPED_REPORT)
        async with app.run_test() as pilot:
            await pilot.press("down", "space")  # unfold type-ignores
            assert "x.py:1" in _labels(app)

            await pilot.press("f")
            await pilot.press("f")

            assert _labels(app)[:3] == ["typing", "type-ignores", "x.py:1"]

    asyncio.run(scenario())


def test_f_folds_metrics_when_the_report_has_no_groups() -> None:
    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test() as pilot:
            await pilot.press("right")
            assert "ranges: python" in _labels(app)

            await pilot.press("f")

            assert _labels(app) == ["noqa-comments", "python-files"]

    asyncio.run(scenario())


def test_f_parks_the_cursor_on_the_group_that_survives_the_fold() -> None:
    async def scenario() -> None:
        app = MetricsApp(GROUPED_REPORT)
        async with app.run_test() as pilot:
            await pilot.press("down", "down")  # onto mypy-overrides, inside typing
            assert _cursor(app) == "mypy-overrides"

            await pilot.press("f")

            assert _cursor(app) == "typing"

    asyncio.run(scenario())


def test_the_arrows_still_work_after_folding_from_inside_a_group() -> None:
    """Regression: the cursor must never be left pointing at a hidden row."""

    async def scenario() -> None:
        app = MetricsApp(GROUPED_REPORT)
        async with app.run_test() as pilot:
            await pilot.press("down", "down")
            await pilot.press("f")

            await pilot.press("down")

            assert _cursor(app) == "lint"

    asyncio.run(scenario())


def test_diff_report_shows_the_branch_impact_and_signed_occurrences() -> None:
    async def scenario() -> None:
        app = MetricsApp(DIFF_REPORT)
        async with app.run_test() as pilot:
            assert _column(app, 2) == ["+2 / -1 (net +1 of 🚧 7)"]

            await pilot.press("right")

            assert _labels(app) == [
                "noqa-comments",
                "ranges: python",
                "src/a.py:3",
                "src/new.py:1",
                "src/b.py:9",
            ]

    asyncio.run(scenario())


def test_metric_rows_carry_their_severity_emoji() -> None:
    async def scenario() -> None:
        app = MetricsApp(
            _summed_report(_valued("a", "g", value=0), _valued("b", "g", value=3))
        )
        async with app.run_test():
            values = _column(app, 2)

            assert any("🎉" in value for value in values)  # measured nothing
            assert any("🚧" in value for value in values)  # 3, against a guide of 100

    asyncio.run(scenario())


def test_group_header_carries_the_sum_of_its_metrics() -> None:
    async def scenario() -> None:
        app = MetricsApp(
            _summed_report(
                _valued("a", "g", value=2, guide=100),
                _valued("b", "g", value=3, guide=100),
            )
        )
        async with app.run_test():
            # 5 against the two metrics' guides added together, not one of them
            assert _column(app, 2)[0] == "🚧 5"

    asyncio.run(scenario())


def test_a_group_summing_to_zero_starts_folded() -> None:
    async def scenario() -> None:
        app = MetricsApp(
            _summed_report(
                _valued("a", "clean", value=0),
                _valued("b", "clean", value=0),
                _valued("c", "dirty", value=4),
            )
        )
        async with app.run_test():
            # nothing to show, so "clean" keeps out of the way
            assert _labels(app) == ["clean", "dirty", "c"]

    asyncio.run(scenario())


def test_a_zero_group_holding_an_error_stays_open() -> None:
    """An error is the one thing that must never be folded out of sight."""

    async def scenario() -> None:
        app = MetricsApp(
            _summed_report(
                _valued("a", "clean", value=0),
                MetricOutcome(
                    spec=MetricSpec(name="b", type="file_count", group="clean"),
                    range_names=(),
                    error="ValueError: boom",
                ),
            )
        )
        async with app.run_test():
            assert _labels(app) == ["clean", "a", "b"]

    asyncio.run(scenario())


def test_an_unchanged_diff_group_starts_folded() -> None:
    """A branch that moved nothing here has nothing to say, whatever it stands on."""

    async def scenario() -> None:
        report = DiffReport(
            root=Path("/proj"),
            source=Path("/proj/tingle.toml"),
            base_ref="main",
            merge_base="abc123",
            outcomes=(
                DiffOutcome(
                    spec=MetricSpec(name="still", type="file_count", group="quiet"),
                    range_names=(),
                    result=DiffResult(net=0, added=0, removed=0),
                    total=MetricResult(value=12),
                ),
                DiffOutcome(
                    spec=MetricSpec(name="moved", type="file_count", group="loud"),
                    range_names=(),
                    result=DiffResult(net=2, added=2, removed=0),
                    total=MetricResult(value=9),
                ),
            ),
        )
        app = MetricsApp(report)
        async with app.run_test():
            assert _labels(app) == ["quiet", "loud", "moved"]

    asyncio.run(scenario())


def test_wasd_is_no_longer_bound() -> None:
    # wasd only ever existed because the arrows were unavailable
    bindings = (*MetricsApp.BINDINGS, *BrowseTable.BINDINGS)
    keys = {b.key for b in bindings if isinstance(b, Binding)}
    assert keys.isdisjoint({"w", "a", "s", "d"})


def test_folding_is_bound_on_the_table_not_the_app() -> None:
    # ctrl+p is taken by the VS Code terminal, so the palette moves to "p"
    assert MetricsApp.ENABLE_COMMAND_PALETTE is True
    assert MetricsApp.COMMAND_PALETTE_BINDING == "p"
    app_bindings = [b for b in MetricsApp.BINDINGS if isinstance(b, Binding)]
    table_bindings = [b for b in BrowseTable.BINDINGS if isinstance(b, Binding)]
    # the arrows must reach the focused table first, so they cannot be
    # app-level: an app binding would need priority, and priority bindings
    # are checked app-down and would steal the palette's own arrows
    assert {b.key for b in app_bindings}.isdisjoint({"up", "down", "left", "right"})
    assert not any(b.priority for b in (*app_bindings, *table_bindings))
    shown = {b.key: b.description for b in table_bindings if b.show}
    assert shown == {"left": "Fold", "right": "Unfold", "space": "Toggle / open"}
    assert all(not b.show for b in table_bindings if b.key in {"h", "j", "k", "l"})


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
    # `down` ran against the palette screen -- doing nothing, yet still
    # reporting the key as handled. Its result list never saw the arrows.
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
            app.pop_screen()
            await pilot.pause()
            assert "type-ignores" in _labels(app)  # "f" folded nothing

    asyncio.run(scenario())


def test_quit_binding() -> None:
    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test() as pilot:
            await pilot.press("q")
            await pilot.pause()
            assert not app.is_running

    asyncio.run(scenario())


def test_the_table_holds_focus_so_the_keys_always_land() -> None:
    async def scenario() -> None:
        app = MetricsApp(RUN_REPORT)
        async with app.run_test():
            assert isinstance(app.focused, BrowseTable)

    asyncio.run(scenario())
