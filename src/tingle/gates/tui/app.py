"""Interactive terminal UI over run and diff reports (textual adapter)."""
from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.app import App
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Collapsible, Footer, Header, Static

from tingle.gates.cli.render import diff_occurrence_lines, occurrence_lines
from tingle.pacts.diff import DiffOutcome

if TYPE_CHECKING:
    from collections.abc import Iterable

    from textual.app import ComposeResult

    from tingle.pacts.diff import DiffReport
    from tingle.pacts.report import MetricOutcome, RunReport


class MetricsApp(App[None]):
    """Accordion of metrics; expand a row to see its occurrences."""

    TITLE = "tingle"
    BINDINGS: ClassVar = [
        Binding("q", "quit", "Quit"),
        Binding("down", "focus_metric(1)", "Next", show=False, priority=True),
        Binding("up", "focus_metric(-1)", "Prev", show=False, priority=True),
    ]

    def __init__(self, report: RunReport | DiffReport) -> None:
        """Present an already-computed report; the TUI never runs metrics."""
        super().__init__()
        self._report = report
        self._name_width = _column_width(o.spec.name for o in self._outcomes)
        self._type_width = _column_width(o.spec.type for o in self._outcomes)

    @property
    def _outcomes(self) -> tuple[MetricOutcome | DiffOutcome, ...]:
        return self._report.outcomes

    def compose(self) -> ComposeResult:
        """Header, one collapsible per metric, and the key legend."""
        yield Header()
        self.sub_title = str(self._report.root)
        with VerticalScroll():
            for index, outcome in enumerate(self._outcomes):
                yield Collapsible(
                    *_detail_widgets(outcome),
                    title=self._title(outcome),
                    id=f"metric-{index}",
                )
        yield Footer()

    def on_mount(self) -> None:
        """Focus the first metric so Up/Down move between rows at once."""
        self.screen.focus_next("CollapsibleTitle")

    def action_focus_metric(self, direction: int) -> None:
        """Move the focus (row cursor) to the next/previous metric header."""
        if direction < 0:
            self.screen.focus_previous("CollapsibleTitle")
        else:
            self.screen.focus_next("CollapsibleTitle")

    def _title(self, outcome: MetricOutcome | DiffOutcome) -> str:
        name = _escape(outcome.spec.name).ljust(self._name_width)
        kind = _escape(outcome.spec.type).ljust(self._type_width)
        return f"{name}  [dim]{kind}[/dim]  {_stats(outcome)}"


def _column_width(names: Iterable[str]) -> int:
    return max((len(name) for name in names), default=0)


def _stats(outcome: MetricOutcome | DiffOutcome) -> str:
    if isinstance(outcome, DiffOutcome):
        if outcome.result is None:
            return "[red]ERROR[/red]"
        added = _signed(outcome.result.added, "red")
        removed = _signed(outcome.result.removed, "green", sign="-")
        total = outcome.total.value if outcome.total else "?"
        net = _net(outcome.result.net)
        return f"{added} / {removed} (net {net} of {total})"
    if outcome.result is None:
        return _with_ranges(outcome, "[red]ERROR[/red]")
    return _with_ranges(outcome, f"[b]{outcome.result.value}[/b]")


def _with_ranges(outcome: MetricOutcome, stat: str) -> str:
    ranges = _escape(", ".join(outcome.range_names))
    return f"{ranges}  {stat}" if ranges else stat


def _signed(value: int | None, style: str, sign: str = "+") -> str:
    if value is None:
        return ""
    if value > 0:
        return f"[{style}]{sign}{value}[/{style}]"
    return "0"


def _net(net: int) -> str:
    if net > 0:
        return f"[red]+{net}[/red]"
    if net < 0:
        return f"[green]{net}[/green]"
    return "0"


def _escape(text: str) -> str:
    """Neutralise Textual markup in dynamic text (metric names, ranges)."""
    return text.replace("\\", "\\\\").replace("[", r"\[")


def _detail_widgets(outcome: MetricOutcome | DiffOutcome) -> list[Static]:
    if outcome.result is None:
        return [Static("[dim](metric failed; see the summary above)[/dim]")]
    if isinstance(outcome, DiffOutcome):
        lines = diff_occurrence_lines(outcome.result)
    else:
        lines = occurrence_lines(outcome.result)
    return [Static(line) for line in lines]
