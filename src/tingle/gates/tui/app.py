"""Interactive terminal UI over run and diff reports (textual adapter)."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.app import App
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Collapsible, Footer, Header, Static
from textual.widgets.collapsible import CollapsibleTitle

from tingle.gates.cli.render import (
    diff_occurrence_lines,
    group_sections,
    occurrence_lines,
)
from tingle.mills.display import group_summary, severity_emoji
from tingle.pacts.diff import DiffOutcome

if TYPE_CHECKING:
    from collections.abc import Iterable

    from textual.app import ComposeResult

    from tingle.pacts.diff import DiffReport
    from tingle.pacts.report import GroupSummary, MetricOutcome, RunReport


class NavCollapsible(Collapsible):
    """A `Collapsible` that steers the accordion with the arrow keys.

    The bindings live here rather than on the app because keys bubble up
    from the focused `CollapsibleTitle`: this widget is its parent, so it
    is offered the arrows before the enclosing `VerticalScroll` can claim
    them for scrolling. Binding them on the app would need `priority`,
    which is checked app-down and would swallow the arrows the command
    palette's own result list needs.
    """

    BINDINGS: ClassVar = [
        Binding("up", "app.focus_metric(-1)", "Prev"),
        Binding("down", "app.focus_metric(1)", "Next"),
        Binding("left", "app.fold", "Fold"),
        Binding("right", "app.unfold", "Unfold"),
        Binding("k", "app.focus_metric(-1)", "Prev", show=False),
        Binding("j", "app.focus_metric(1)", "Next", show=False),
        Binding("h", "app.fold", "Fold", show=False),
        Binding("l", "app.unfold", "Unfold", show=False),
    ]


class MetricsApp(App[None]):
    """Three-level accordion: group -> metric -> file results.

    Groups and their metric rows are visible at rest; each group and
    metric folds and unfolds independently (arrows or Enter), a metric
    revealing its occurrences.
    """

    TITLE = "tingle"
    # ctrl+p (the default) is swallowed by the VS Code terminal; there is
    # no text input to steal a bare "p" from, so bind the palette to that
    COMMAND_PALETTE_BINDING = "p"
    CSS = """
    Collapsible.group > CollapsibleTitle { text-style: bold; }
    """
    # navigation lives on NavCollapsible, not here: an app-level arrow
    # binding would have to be priority to beat the scroll container, and
    # priority bindings are checked app-down, stealing the arrows from the
    # command palette.
    BINDINGS: ClassVar = [
        Binding("space", "toggle_fold", "Toggle"),
        Binding("f", "toggle_fold_all", "Fold all"),
        Binding("q", "quit", "Quit"),
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
        """Header, the grouped metric accordion, and the key legend."""
        yield Header()
        self.sub_title = str(self._report.root)
        sections = group_sections(self._outcomes)
        grouped = any(name is not None for name, _ in sections)
        index = 0
        # can_focus=False: a click on the empty space below the rows -- or on
        # the way back to a terminal window that lost focus -- would otherwise
        # land on the scroll container and focus it. The arrows are bound on
        # NavCollapsible and reach it only by bubbling from a focused header,
        # so with the container holding focus they scroll instead of
        # navigating, and nothing but clicking a row hands focus back.
        with VerticalScroll(can_focus=False):
            for section, (name, outcomes) in enumerate(sections):
                metrics: list[NavCollapsible] = []
                for outcome in outcomes:
                    metrics.append(
                        NavCollapsible(
                            *_detail_widgets(outcome),
                            title=self._title(outcome),
                            id=f"metric-{index}",
                            classes="metric",
                        )
                    )
                    index += 1
                if grouped:
                    summary = group_summary(outcomes)
                    yield NavCollapsible(
                        *metrics,
                        title=_group_title(name, summary),
                        collapsed=_starts_folded(summary),
                        id=f"group-{section}",
                        classes="group",
                    )
                else:
                    yield from metrics
        yield Footer()

    def on_mount(self) -> None:
        """Focus the first header so Up/Down move between rows at once."""
        self.screen.focus_next("CollapsibleTitle")

    def action_focus_metric(self, direction: int) -> None:
        """Move focus to the next/previous header (group or metric)."""
        if direction < 0:
            self.screen.focus_previous("CollapsibleTitle")
        else:
            self.screen.focus_next("CollapsibleTitle")

    def action_unfold(self) -> None:
        """Unfold (right arrow) the focused group/metric header."""
        if (collapsible := self._focused_collapsible()) is not None:
            collapsible.collapsed = False

    def action_fold(self) -> None:
        """Fold (left arrow) the focused group/metric header."""
        if (collapsible := self._focused_collapsible()) is not None:
            collapsible.collapsed = True

    def action_toggle_fold(self) -> None:
        """Toggle (space) the focused group/metric header."""
        if (collapsible := self._focused_collapsible()) is not None:
            collapsible.collapsed = not collapsible.collapsed

    def action_toggle_fold_all(self) -> None:
        """Fold/unfold every group (f), leaving file results as they are.

        Groups are the headers that hold metric rows, so this collapses
        the listing to its group titles and back. A groupless report has
        no group headers, so there the metric rows are the top level and
        fold instead. Unfolds only once nothing is left unfolded.
        """
        if not (headers := self._fold_all_targets()):
            return
        collapsed = any(not header.collapsed for header in headers)
        # Folding hides any header nested in a group, and textual drops
        # focus along with it. The arrows live on NavCollapsible, so an
        # unfocused app has no arrows to focus anything again -- park the
        # cursor on the enclosing header, which stays visible.
        landing = self._enclosing_header(headers) or headers[0]
        for header in headers:
            header.collapsed = collapsed
        if collapsed:
            landing.query_one(CollapsibleTitle).focus()

    def _fold_all_targets(self) -> list[Collapsible]:
        groups = list(self.query(".group").results(Collapsible))
        return groups or list(self.query(".metric").results(Collapsible))

    def _enclosing_header(self, headers: list[Collapsible]) -> Collapsible | None:
        """Find the fold-all target containing the focused widget, if any."""
        if (focused := self.focused) is None:
            return None
        return next((a for a in focused.ancestors_with_self if a in headers), None)

    def _focused_collapsible(self) -> Collapsible | None:
        if (focused := self.focused) is None:
            return None
        return next(
            (a for a in focused.ancestors_with_self if isinstance(a, Collapsible)), None
        )

    def _title(self, outcome: MetricOutcome | DiffOutcome) -> str:
        name = _escape(outcome.spec.name).ljust(self._name_width)
        kind = _escape(outcome.spec.type).ljust(self._type_width)
        return f"{name}  [dim]{kind}[/dim]  {_stats(outcome)}"


def _column_width(names: Iterable[str]) -> int:
    return max((len(name) for name in names), default=0)


def _group_title(name: str | None, summary: GroupSummary) -> str:
    """Render the group's name, then what its metrics add up to.

    A diff shows the net beside the standing total, since a group's header
    has to answer both "what did the branch do" and "where does it stand".
    """
    label = _escape(name) if name is not None else "(ungrouped)"
    stat = f"{severity_emoji(summary.value, summary.guide)} [b]{summary.value}[/b]"
    if summary.net is not None:
        return f"{label}  net {_net(summary.net)} of {stat}"
    return f"{label}  {stat}"


def _starts_folded(summary: GroupSummary) -> bool:
    """Fold a group with nothing to show, unless it is hiding an error.

    A run's group is empty when it measured nothing at all; a branch's when
    it moved nothing. An error is never folded away -- it is the one thing
    the reader most needs to see.
    """
    if summary.has_error:
        return False
    if summary.net is not None:
        return not summary.changed
    return summary.value == 0


def _stats(outcome: MetricOutcome | DiffOutcome) -> str:
    if isinstance(outcome, DiffOutcome):
        if outcome.result is None:
            return "[red]ERROR[/red]"
        added = _signed(outcome.result.added, "red")
        removed = _signed(outcome.result.removed, "green", sign="-")
        net = _net(outcome.result.net)
        if outcome.total is None:
            return f"{added} / {removed} (net {net} of ?)"
        # the emoji ranks the standing debt, which is what the total is
        emoji = severity_emoji(outcome.total.value, outcome.guide)
        return f"{added} / {removed} (net {net} of {emoji} {outcome.total.value})"
    if outcome.result is None:
        return _with_ranges(outcome, "[red]ERROR[/red]")
    value = outcome.result.value
    emoji = severity_emoji(value, outcome.guide)
    return _with_ranges(outcome, f"{emoji} [b]{value}[/b]")


def _with_ranges(outcome: MetricOutcome, stat: str) -> str:
    ranges = _escape(", ".join(outcome.range_names))
    return f"{ranges}  {stat}" if ranges else stat


def _signed(value: int | None, style: str, *, sign: str = "+") -> str:
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
    lines = (
        diff_occurrence_lines(outcome.result)
        if isinstance(outcome, DiffOutcome)
        else occurrence_lines(outcome.result)
    )
    return [Static(line) for line in lines]
