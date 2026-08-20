"""Interactive terminal UI over run and diff reports (textual adapter).

The table is drawn from the browse service, which decides what is visible
and in what order; nothing here reads an outcome or resolves a fold. This
module's whole job is turning `Row`s into cells and keys into gestures.

The run itself happens here too, on a worker thread, because a report
collected before the app started would be a wait with nothing on screen
to explain it.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, ClassVar, TypeAlias

from rich.cells import cell_len
from rich.text import Text
from textual.app import App
from textual.binding import Binding
from textual.message import Message
from textual.widgets import DataTable, Footer, Header, Input, Static

from tingle.gates.cli.textual.loading import LoadingScreen
from tingle.pacts.browse import RowKind, SortKey
from tingle.pacts.config import SelectionError
from tingle.pacts.diff import DiffReport, DiffSourceError
from tingle.pacts.editor import EditorError

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from textual.app import ComposeResult

    from tingle.pacts.browse import BrowseState, Row
    from tingle.pacts.editor import EditorOpener
    from tingle.pacts.metrics import ProgressSink, RunProgress
    from tingle.pacts.report import RunReport
    from tingle.pacts.services import BrowseServiceProtocol

#: Starts the run and hands back what it came to, reporting its progress
#: to the sink it is given. The gate binds the selection and the base
#: before handing it over, so the app starts a run without knowing what
#: kind of run it is.
Collect: TypeAlias = "Callable[[ProgressSink], RunReport | DiffReport]"

#: How long the run gets to finish before anything is drawn to say it is
#: happening. A screen that flashes up and vanishes is worse than a beat
#: of stillness, and on a small project the whole run fits in here.
REVEAL_AFTER = 0.25

#: Marks a row that can be folded, open and shut.
UNFOLDED, FOLDED = "▾ ", "▸ "

#: Sits where a marker would on a row that cannot be folded, so the labels
#: of siblings line up whether or not they have anything underneath them.
NO_MARKER = "  "

#: One level of the outline.
INDENT = "  "

#: The column headings, in the order they are added, each with the key the
#: table knows it by. Stated once: the header marking reads them back to
#: rebuild a label rather than stripping last redraw's arrow off the widget.
COLUMNS = (("Group / Metric", "label"), ("Type", "type"), ("Value", "value"))

#: Which column each sort key lives in, so the header of the one in charge
#: can be picked out. Group and name share the first column; score shares
#: the third with value, being the emoji that column already leads with.
SORT_COLUMNS = {
    SortKey.GROUP: 0,
    SortKey.NAME: 0,
    SortKey.TYPE: 1,
    SortKey.VALUE: 2,
    SortKey.SCORE: 2,
}

#: Marks the header of the column currently deciding the order.
ASCENDING, DESCENDING = " ▲", " ▼"

#: Stands in for that marker on the columns not currently deciding it. A
#: column is measured against its heading when it is added and never
#: again, so every heading claims the room for a marker from the start;
#: one that grew it later would have it cut off wherever the column's own
#: values left it narrow.
MARKER_ROOM = " " * cell_len(ASCENDING)

#: Separates the sort stack, most significant first.
SORT_SEPARATOR = " then "


class BrowseTable(DataTable[Text]):
    """The outline, spending the side arrows on folding.

    A row cursor has nowhere to go sideways, so the left and right the
    table would spend on columns are free for the outline. They are bound
    here rather than on the app because a focused widget is offered a key
    before the app is, so an app-level binding would never see them.
    """

    BINDINGS: ClassVar = [
        Binding("left", "app.fold", "Fold"),
        Binding("right", "app.unfold", "Unfold"),
        Binding("h", "app.fold", "Fold", show=False),
        Binding("l", "app.unfold", "Unfold", show=False),
        Binding("k", "cursor_up", "Prev", show=False),
        Binding("j", "cursor_down", "Next", show=False),
        Binding("space", "app.select_row", "Toggle / open"),
        Binding("enter", "app.select_row", "Toggle / open", show=False),
    ]


class SortBar(Static):
    """One line saying why the rows are in the order they are in.

    Without it a stacked sort is guesswork: the reader can see that the
    order changed but not which key is deciding it, nor which earlier key
    is still breaking its ties.
    """


class SearchBar(Input):
    """The `/` query, and the only thing on screen that eats bare letters.

    Every letter the app binds -- fold, quit, the five sorts and their
    shifted twins -- has to reach this as text while it holds focus.
    Textual offers a key to the focused widget first, so an Input gets
    them all; escape is bound here to give the reader a way back out.
    """

    BINDINGS: ClassVar = [Binding("escape", "app.end_search", "Leave search")]


@dataclass
class Measured:
    """What the run inside the app has come to so far.

    One object rather than three attributes because they are one fact
    read at three moments: what the run last said, what it finally came
    to, and why it could not. The gate reads the last two after the app
    has closed, which is the only way a report leaves a terminal.
    """

    latest: RunProgress | None = None
    report: RunReport | DiffReport | None = None
    failure: Exception | None = None

    @property
    def over(self) -> bool:
        """Whether the run has stopped, whichever way it stopped."""
        return self.report is not None or self.failure is not None


class RunProgressed(Message):
    """How far the run inside the app has got."""

    def __init__(self, progress: RunProgress) -> None:
        """Carry one progress report across from the worker thread."""
        super().__init__()
        self.progress = progress


class RunFinished(Message):
    """The run is done, and this is what it came to."""

    def __init__(self, report: RunReport | DiffReport) -> None:
        """Carry the finished report across from the worker thread."""
        super().__init__()
        self.report = report


class RunFailed(Message):
    """The run could not be done, for a reason the command line knows."""

    def __init__(self, error: Exception) -> None:
        """Carry the failure across from the worker thread."""
        super().__init__()
        self.error = error


class MetricsApp(App[None]):
    """Everything a run measured, as one foldable table.

    Group headers, the metrics under them and -- once a metric is
    unfolded -- what it measures and every hit it located, all in the same
    table. The cursor moves by row; left and right fold and unfold, space
    toggles, and space on a located hit opens it in the editor.
    """

    TITLE = "tingle"
    # ctrl+p (the default) is swallowed by the VS Code terminal; there is
    # no text input to steal a bare "p" from, so bind the palette to that
    COMMAND_PALETTE_BINDING = "p"
    CSS = """
    BrowseTable { height: 1fr; }
    SortBar { height: auto; color: $text-muted; }
    SearchBar { border: none; height: 1; padding: 0 1; }
    SearchBar.hidden { display: none; }
    """
    BINDINGS: ClassVar = [
        Binding("slash", "search", "Search"),
        Binding("f", "toggle_fold_all", "Fold all"),
        # value and score are both bound because they answer different
        # questions: what is biggest, and what is worst
        Binding("g", "sort('group')", "Sort group"),
        Binding("n", "sort('name')", "Sort name"),
        Binding("t", "sort('type')", "Sort type"),
        Binding("v", "sort('value')", "Sort value"),
        Binding("c", "sort('score')", "Sort score"),
        # the shifted letter is the same sort the other way up, so the
        # reader asks for a direction rather than remembering which one
        # each key happens to prefer
        Binding("G", "sort_desc('group')", "Sort group desc", show=False),
        Binding("N", "sort_desc('name')", "Sort name desc", show=False),
        Binding("T", "sort_desc('type')", "Sort type desc", show=False),
        Binding("V", "sort_desc('value')", "Sort value desc", show=False),
        Binding("C", "sort_desc('score')", "Sort score desc", show=False),
        Binding("0", "clear_sort", "Reset sort"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        root: Path,
        *,
        collect: Collect,
        opener: EditorOpener,
        browse: BrowseServiceProtocol,
    ) -> None:
        """Open on an empty table, and start the run that will fill it.

        The session begins over no sections rather than over none at all,
        so every gesture is answerable from the first frame: they act on
        an empty outline until the report lands and replaces it.
        """
        super().__init__()
        self._root = root
        self._collect = collect
        self._opener = opener
        self._browse = browse
        self._state = browse.start(())
        self._rows: tuple[Row, ...] = ()
        self.measured = Measured()

    def compose(self) -> ComposeResult:
        """Header, the table the whole report lives in, and the key legend."""
        yield Header()
        self.sub_title = str(self._root)
        table = BrowseTable(cursor_type="row")
        for heading, key in COLUMNS:
            table.add_column(heading + MARKER_ROOM, key=key)
        yield table
        yield SearchBar(placeholder="search", classes="hidden")
        yield SortBar()
        yield Footer()

    def on_mount(self) -> None:
        """Start measuring, and arrange to say so if it takes a moment."""
        self.set_timer(REVEAL_AFTER, self._show_loading)
        self.query_one(BrowseTable).focus()
        # off the event loop: the run reads the whole tree, and the app has
        # to stay answerable -- and redrawable -- the entire time
        self.run_worker(self._measure, thread=True)

    def _show_loading(self) -> None:
        """Put the loading screen up, if the run is still going by now.

        Asking whether the run is over beats holding the timer and
        stopping it: the question has an answer either way round, so the
        two cannot race.

        It opens on the last thing the run said rather than on nothing:
        the run has been going since before there was anywhere to show it.
        """
        if self.measured.over:
            return
        self.push_screen(LoadingScreen(self.measured.latest))

    def _measure(self) -> None:
        """Run the metrics, off the event loop, and report back either way.

        The two failures caught here are the ones the command line already
        knows how to print: they are carried out rather than handled, so
        the gate keeps deciding what a bad selection or an unreachable
        base means. Anything else is a bug and is left to crash loudly.
        """
        try:
            report = self._collect(self._note)
        except (SelectionError, DiffSourceError) as exc:
            self.post_message(RunFailed(exc))
        else:
            self.post_message(RunFinished(report))

    def _note(self, progress: RunProgress) -> None:
        """Take a progress report from the worker thread onto the loop.

        `post_message` is thread-safe, so the walk hands over its count
        without bouncing every report through a call into the loop.
        """
        self.post_message(RunProgressed(progress))

    def on_run_progressed(self, event: RunProgressed) -> None:
        """Keep the latest, and show it if there is a screen up to show it."""
        self.measured.latest = event.progress
        if isinstance(self.screen, LoadingScreen):
            self.screen.advance(event.progress)

    def on_run_finished(self, event: RunFinished) -> None:
        """Fill the table with what the run came to, and get out of its way."""
        self.measured.report = event.report
        self._state = self._browse.fold_quiet_groups(
            self._browse.start(event.report.sections)
        )
        self._hide_loading()
        self._draw()
        self.query_one(BrowseTable).focus()

    def on_run_failed(self, event: RunFailed) -> None:
        """Leave, carrying the failure out to the gate that can report it."""
        self.measured.failure = event.error
        self._hide_loading()
        self.exit()

    def _hide_loading(self) -> None:
        """Take the loading screen down, if one ever went up."""
        if isinstance(self.screen, LoadingScreen):
            self.pop_screen()

    def action_fold(self) -> None:
        """Fold the row the cursor is on, or the metric that holds it."""
        if (row := self._fold_target()) is None:
            return
        self._state = self._browse.set_fold(self._state, row.key, folded=True)
        self._draw(land_on=row.key)

    def action_unfold(self) -> None:
        """Unfold the folded row the cursor is on."""
        if (row := self._current()) is None or row.folded is not True:
            return
        self._state = self._browse.set_fold(self._state, row.key, folded=False)
        self._draw(land_on=row.key)

    def action_select_row(self) -> None:
        """Open a located hit, or fold and unfold anything that folds."""
        if (row := self._current()) is None:
            return
        if row.kind is RowKind.OCCURRENCE:
            self._open(row)
        elif row.folded is not None:
            self._state = self._browse.set_fold(
                self._state, row.key, folded=not row.folded
            )
            self._draw(land_on=row.key)

    def action_sort(self, key: str) -> None:
        """Sort upwards by `key`, keeping the stack below it as ties."""
        self._push_sort(key, descending=False)

    def action_sort_desc(self, key: str) -> None:
        """Sort downwards by `key`: the same sort turned over."""
        self._push_sort(key, descending=True)

    def _push_sort(self, key: str, *, descending: bool) -> None:
        """Push the sort a binding named; the binding names the key itself."""
        self._state = self._browse.push_sort(
            self._state, SortKey(key), descending=descending
        )
        self._draw()

    def action_clear_sort(self) -> None:
        """Drop every sort, bringing back config order and the outline."""
        self._state = self._browse.clear_sort(self._state)
        self._draw()

    def action_search(self) -> None:
        """Open the query box and put the cursor in it."""
        search = self.query_one(SearchBar)
        search.remove_class("hidden")
        search.focus()

    def action_end_search(self) -> None:
        """Leave search mode, restoring the outline the reader had.

        The query goes with the mode, and so does every fold made while it
        was up -- the model drops the overlay when the query empties, so
        the outline comes back exactly as it was left.
        """
        search = self.query_one(SearchBar)
        search.value = ""
        search.add_class("hidden")
        self._state = self._browse.set_query(self._state, "")
        self._draw()
        self.query_one(BrowseTable).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter as the query is typed, so the reader sees it narrowing."""
        self._state = self._browse.set_query(self._state, event.value)
        self._draw()

    def on_input_submitted(self, _: Input.Submitted) -> None:
        """Enter hands the rows back without giving up the query."""
        self.query_one(BrowseTable).focus()

    def action_toggle_fold_all(self) -> None:
        """Collapse the listing to its top row and back.

        The cursor is parked on the row that survives the fold before the
        fold happens, or it would be left pointing at a hidden row.
        """
        landing = self._enclosing_key()
        self._state = self._browse.toggle_fold_all(self._state)
        self._draw(land_on=landing)

    def _draw(self, *, land_on: str | None = None) -> None:
        """Redraw from the model, keeping the cursor where it belongs.

        `land_on` is the row a gesture acted on, which is the row that is
        still there afterwards; without one the cursor keeps its place.
        """
        table = self.query_one(BrowseTable)
        wanted = land_on if land_on is not None else self._cursor_key()
        self._rows = self._browse.rows(self._state)
        table.clear()
        for row in self._rows:
            table.add_row(*_cells(row), key=row.key)
        table.move_cursor(row=self._index_of(wanted))
        _mark_sorted_header(table, self._state)
        self.query_one(SortBar).update(
            _sort_line(self._state, self._browse, rows=self._rows)
        )

    def _current(self) -> Row | None:
        """Return the row the cursor is on, if the table has any."""
        cursor = self.query_one(BrowseTable).cursor_row
        if 0 <= cursor < len(self._rows):
            return self._rows[cursor]
        return None

    def _cursor_key(self) -> str | None:
        return row.key if (row := self._current()) is not None else None

    def _index_of(self, key: str | None) -> int:
        """Where `key` sits now, or the top if the redraw left it behind."""
        if key is None:
            return 0
        return next(
            (index for index, row in enumerate(self._rows) if row.key == key), 0
        )

    def _fold_target(self) -> Row | None:
        """Find what a fold acts on: this row, or the metric it belongs to.

        Folding from a detail or a hit folds the metric above it, which is
        what makes the left arrow read as "out of here" rather than as a
        key that does nothing on most of the rows it can reach.
        """
        if (row := self._current()) is None:
            return None
        if row.folded is not None:
            return row
        return self._row(row.parent) if row.parent is not None else None

    def _enclosing_key(self) -> str | None:
        """Find the top-level row holding the cursor: where fold-all leaves it."""
        row = self._current()
        while row is not None and row.parent is not None:
            row = self._row(row.parent)
        return row.key if row is not None else None

    def _row(self, key: str) -> Row | None:
        return next((row for row in self._rows if row.key == key), None)

    def _open(self, row: Row) -> None:
        """Open a hit where the reader writes code, if there is one to open."""
        if row.occurrence is None:  # pragma: no cover - guarded by caller
            return
        if not self._opener.available:
            self.notify("No VS Code terminal to open in.", severity="warning")
            return
        target = str(self._root / row.occurrence.path)
        line = row.occurrence.line
        # off the event loop: handing the file over means waiting on
        # another process, and the table must stay answerable meanwhile
        self.run_worker(
            partial(self._hand_over, target, line), thread=True, exit_on_error=False
        )

    def _hand_over(self, target: str, line: int | None) -> None:
        """Ask the editor for the file, and say so if it will not take it."""
        try:
            self._opener.open(target, line)
        except EditorError as exc:
            self.call_from_thread(self.notify, str(exc), severity="error")


def _mark_sorted_header(table: BrowseTable, state: BrowseState) -> None:
    """Point the column headings at the one currently deciding the order.

    The arrow says which way that column is running, which the labels
    alone cannot: `value` and `score` share a column, and either can be
    pointing either way.
    """
    primary = state.sort[0] if state.sort else None
    marked = SORT_COLUMNS[primary.key] if primary is not None else None
    columns = zip(COLUMNS, table.columns.values(), strict=True)
    for index, ((heading, _key), column) in enumerate(columns):
        arrow = (
            (DESCENDING if primary.descending else ASCENDING)
            if primary is not None and index == marked
            else ""
        )
        # the marker takes the place the heading already left for it, so
        # every label is the width the column was measured against
        column.label = Text(
            heading + (arrow or MARKER_ROOM), style="bold" if arrow else ""
        )
    table.refresh()


def _sort_line(
    state: BrowseState, browse: BrowseServiceProtocol, *, rows: tuple[Row, ...]
) -> str:
    """Say what is deciding the order, and what it cost the outline.

    A flattened view is worth saying out loud: the reader has just lost
    the group headers, and the way back is one key they cannot see from
    the rows alone. A live query says so instead: while one is up it is
    the thing deciding what is on screen, and escape is the way out of
    it.

    The rows counted are the ones just drawn: projecting them again would
    rescan every occurrence of every metric, once per keystroke typed.
    """
    if (search := state.search) is not None:
        found = sum(1 for row in rows if row.kind is RowKind.METRIC)
        matched = f"{found} metric{'' if found == 1 else 's'}"
        return f"search: {search.query!r} — {matched} — esc to leave"
    if not state.sort:
        return "sort: config order"
    stack = SORT_SEPARATOR.join(
        f"{step.key.value} {'desc' if step.descending else 'asc'}"
        for step in state.sort
    )
    if browse.outlined(state):
        return f"sort: {stack}"
    return f"sort: {stack}  ·  flat, no groups — 0 to reset"


def _cells(row: Row) -> tuple[Text, Text, Text]:
    """Render one row: the outline in the first column, then type and value.

    Every cell is a `Text`, not markup, so a metric named `[b]` is a
    metric named `[b]` rather than an instruction to the renderer.
    """
    label, kind, value = row.cells
    outline = Text.assemble(
        INDENT * row.depth, _marker(row), (label, _label_style(row))
    )
    return (outline, Text(kind, style="dim"), Text(value))


def _marker(row: Row) -> str:
    if row.folded is None:
        return NO_MARKER
    return FOLDED if row.folded else UNFOLDED


def _label_style(row: Row) -> str:
    if row.kind is RowKind.GROUP:
        return "bold"
    if row.kind is RowKind.DETAIL:
        return "dim italic"
    return ""
