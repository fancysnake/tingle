"""Interactive terminal UI over run and diff reports (textual adapter)."""
from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from rich.text import Text
from textual.app import App
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from tingle.gates.cli.render import diff_occurrence_lines, occurrence_lines
from tingle.pacts.diff import DiffOutcome, DiffReport

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from tingle.pacts.report import MetricOutcome, RunReport

RUN_COLUMNS = ("Metric", "Type", "Ranges", "Value")
DIFF_COLUMNS = ("Metric", "Type", "Added", "Removed", "Net", "Total")


class MetricsApp(App[None]):
    """Sortable metrics table; Enter opens a metric's occurrences."""

    TITLE = "tingle"
    BINDINGS: ClassVar = [
        Binding("q", "quit", "Quit"),
        *(
            Binding(str(number), f"sort({number})", "Sort", show=False)
            for number in range(1, len(DIFF_COLUMNS) + 1)
        ),
    ]

    def __init__(self, report: RunReport | DiffReport) -> None:
        """Present an already-computed report; the TUI never runs metrics."""
        super().__init__()
        self._report = report
        self._columns = (
            DIFF_COLUMNS if isinstance(report, DiffReport) else RUN_COLUMNS
        )
        self._sort_column: int | None = None
        self._sort_reverse = False

    def compose(self) -> ComposeResult:
        """Header, the metrics table, and the key legend."""
        yield Header()
        yield DataTable[Text]()
        yield Footer()

    @property
    def _outcomes(self) -> tuple[MetricOutcome | DiffOutcome, ...]:
        return self._report.outcomes

    def on_mount(self) -> None:
        """Fill the table from the report."""
        self.sub_title = str(self._report.root)
        table: DataTable[Text] = self.query_one(DataTable)
        table.cursor_type = "row"
        for index, column in enumerate(self._columns):
            table.add_column(column, key=str(index))
        for index, outcome in enumerate(self._outcomes):
            table.add_row(*_cells(outcome), key=str(index))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Enter on a row opens the occurrence detail screen."""
        if event.row_key.value is None:
            return
        self.push_screen(DetailScreen(self._outcomes[int(event.row_key.value)]))

    def action_sort(self, number: int) -> None:
        """Sort by the 1-based column; same column again flips direction."""
        index = number - 1
        if index >= len(self._columns):
            return
        self._sort_reverse = self._sort_column == index and not self._sort_reverse
        self._sort_column = index
        table: DataTable[Text] = self.query_one(DataTable)
        table.sort(str(index), key=_sort_value, reverse=self._sort_reverse)


class DetailScreen(Screen[None]):
    """Occurrences of a single metric."""

    BINDINGS: ClassVar = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("q", "app.quit", "Quit"),
    ]

    def __init__(self, outcome: MetricOutcome | DiffOutcome) -> None:
        """Show one outcome's occurrences (or its error)."""
        super().__init__()
        self._outcome = outcome

    def compose(self) -> ComposeResult:
        """Heading plus a scrollable occurrence list."""
        yield Header()
        yield Static(_heading(self._outcome), classes="detail-heading")
        yield VerticalScroll(
            *(Static(line) for line in _detail_lines(self._outcome))
        )
        yield Footer()


def _cells(outcome: MetricOutcome | DiffOutcome) -> tuple[Text, ...]:
    name = Text(outcome.spec.name)
    kind = Text(outcome.spec.type)
    if isinstance(outcome, DiffOutcome):
        if outcome.result is None:
            return (name, kind, Text(""), Text(""), Text("ERROR", "red"), Text(""))
        return (
            name,
            kind,
            _signed(outcome.result.added, positive_style="red"),
            _signed(outcome.result.removed, positive_style="green", sign="-"),
            _net(outcome.result.net),
            Text(str(outcome.total.value) if outcome.total else ""),
        )
    if outcome.result is None:
        return (name, kind, Text(", ".join(outcome.range_names)), Text("ERROR", "red"))
    return (
        name,
        kind,
        Text(", ".join(outcome.range_names)),
        Text(str(outcome.result.value)),
    )


def _sort_value(cell: Text) -> tuple[int, float, str]:
    """Numbers sort numerically and before any text."""
    plain = cell.plain.strip()
    try:
        return (0, float(plain.replace("+", "", 1)), "")
    except ValueError:
        return (1, 0.0, plain.lower())


def _signed(value: int | None, positive_style: str, sign: str = "+") -> Text:
    if value is None:
        return Text("")
    if value > 0:
        return Text(f"{sign}{value}", style=positive_style)
    return Text("0")


def _net(net: int) -> Text:
    if net > 0:
        return Text(f"+{net}", style="red")
    if net < 0:
        return Text(str(net), style="green")
    return Text("0")


def _heading(outcome: MetricOutcome | DiffOutcome) -> Text:
    if outcome.error is not None:
        return Text(
            f"{outcome.spec.name} ({outcome.spec.type}): {outcome.error}",
            style="bold red",
        )
    if isinstance(outcome, DiffOutcome):
        if outcome.result is None:
            return Text(outcome.spec.name, style="bold")
        total = outcome.total.value if outcome.total else "?"
        return Text(
            f"{outcome.spec.name} ({outcome.spec.type}):"
            f" net {outcome.result.net:+d} of {total} total",
            style="bold",
        )
    if outcome.result is None:
        return Text(outcome.spec.name, style="bold")
    return Text(
        f"{outcome.spec.name} ({outcome.spec.type}): {outcome.result.value}",
        style="bold",
    )


def _detail_lines(outcome: MetricOutcome | DiffOutcome) -> list[Text]:
    if outcome.result is None:
        return [Text("  (metric failed; see heading)", style="dim")]
    if isinstance(outcome, DiffOutcome):
        return diff_occurrence_lines(outcome.result)
    return occurrence_lines(outcome.result)
