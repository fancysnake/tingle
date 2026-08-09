"""Interactive terminal UI over run and diff reports (textual adapter).

The table is drawn from the browse service, which decides what is visible
and in what order; nothing here reads an outcome or resolves a fold. This
module's whole job is turning `Row`s into cells and keys into gestures.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, ClassVar

from rich.cells import cell_len
from rich.text import Text
from textual.app import App
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Input, Static

from tingle.pacts.browse import RowKind, SortKey
from tingle.pacts.editor import EditorError

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from tingle.pacts.browse import BrowseState, Row
    from tingle.pacts.diff import DiffReport
    from tingle.pacts.editor import EditorOpener
    from tingle.pacts.report import RunReport
    from tingle.pacts.services import BrowseServiceProtocol

#: Marks a row that can be folded, open and shut.
UNFOLDED, FOLDED = "▾ ", "▸ "

#: Sits where a marker would on a row that cannot be folded, so the labels
#: of siblings line up whether or not they have anything underneath them.
NO_MARKER = "  "

#: One level of the outline.
INDENT = "  "

#: Which key sorts by what. Value and score are both here because they
#: answer different questions: what is biggest, and what is worst.
#:
#: The letter sorts upwards and the shifted letter sorts downwards, so the
#: reader asks for a direction rather than remembering which one each key
#: happens to prefer.
SORT_KEYS = {
    "g": SortKey.GROUP,
    "n": SortKey.NAME,
    "t": SortKey.TYPE,
    "v": SortKey.VALUE,
    "c": SortKey.SCORE,
}

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
        Binding("g", "sort('g')", "Sort group"),
        Binding("n", "sort('n')", "Sort name"),
        Binding("t", "sort('t')", "Sort type"),
        Binding("v", "sort('v')", "Sort value"),
        Binding("c", "sort('c')", "Sort score"),
        # the shifted letter is the same sort the other way up
        Binding("G", "sort_desc('g')", "Sort group desc", show=False),
        Binding("N", "sort_desc('n')", "Sort name desc", show=False),
        Binding("T", "sort_desc('t')", "Sort type desc", show=False),
        Binding("V", "sort_desc('v')", "Sort value desc", show=False),
        Binding("C", "sort_desc('c')", "Sort score desc", show=False),
        Binding("0", "clear_sort", "Reset sort"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        report: RunReport | DiffReport,
        opener: EditorOpener,
        *,
        browse: BrowseServiceProtocol,
    ) -> None:
        """Present an already-computed report; the TUI never runs metrics."""
        super().__init__()
        self._report = report
        self._opener = opener
        self._browse = browse
        self._state = browse.fold_quiet_groups(browse.start(report.outcomes))
        self._rows: tuple[Row, ...] = ()

    def compose(self) -> ComposeResult:
        """Header, the table the whole report lives in, and the key legend."""
        yield Header()
        self.sub_title = str(self._report.root)
        table = BrowseTable(cursor_type="row")
        table.add_column("Group / Metric", key="label")
        table.add_column("Type", key="type")
        table.add_column("Value", key="value")
        yield table
        yield SearchBar(placeholder="search", classes="hidden")
        yield SortBar()
        yield Footer()

    def on_mount(self) -> None:
        """Fill the table and put the cursor on its first row."""
        self._draw()
        self.query_one(BrowseTable).focus()

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
        if (sort := SORT_KEYS.get(key)) is not None:
            self._state = self._browse.push_sort(
                self._state, sort, descending=descending
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
        self.query_one(SortBar).update(_sort_line(self._state, self._browse))

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
        target = str(self._report.root / row.occurrence.path)
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
    for index, column in enumerate(table.columns.values()):
        label = _unmarked(str(column.label))
        if index == marked and primary is not None:
            arrow = DESCENDING if primary.descending else ASCENDING
            column.label = Text(label + arrow, style="bold")
        else:
            column.label = Text(label)
        # a column is only ever measured against the cells put in it, so one
        # whose heading just grew an arrow has to claim the room for it --
        # otherwise the arrow is cut off any column its values left narrow
        column.content_width = max(column.content_width, cell_len(column.label.plain))
    table.refresh()


def _unmarked(label: str) -> str:
    """Take last redraw's arrow back off a heading, if it had one.

    Whole suffixes rather than a set of characters to strip: a heading is
    allowed to end in an arrow of its own, and only the one this put there
    should come off.
    """
    for marker in (ASCENDING, DESCENDING):
        label = label.removesuffix(marker)
    return label


def _sort_line(state: BrowseState, browse: BrowseServiceProtocol) -> str:
    """Say what is deciding the order, and what folding costs.

    A flattened view is worth saying out loud: the reader has just lost
    the group outline and every occurrence row with it, and the way back
    is one key they cannot see from the rows alone. A live query says so
    instead: while one is up it is the thing deciding what is on screen,
    and escape is the way out of it.
    """
    if state.query:
        found = sum(1 for row in browse.rows(state) if row.kind is RowKind.METRIC)
        matched = f"{found} metric{'' if found == 1 else 's'}"
        return f"search: {state.query!r} — {matched} — esc to leave"
    if not state.sort:
        return "sort: config order"
    stack = SORT_SEPARATOR.join(
        f"{step.key.value} {'desc' if step.descending else 'asc'}"
        for step in state.sort
    )
    if browse.outlined(state):
        return f"sort: {stack}"
    return f"sort: {stack}  ·  flat, no folding — 0 to reset"


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
