"""Browsing a finished run: what is visible, and in what order.

One question is answered here -- given a report's outcomes, the sort
stack, the search query and the fold set, which rows should be drawn --
so that the interactive gate holds no view logic of its own and can be
tested without a terminal.

Every function is pure: `BrowseState` goes in, a new `BrowseState` or a
list of rows comes out. Nothing here reads a file, runs a metric, or
knows what a widget is.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from tingle.mills.display import group_summary, severity_ratio
from tingle.pacts.browse import BrowseState, Row, RowKind, Sort, SortKey
from tingle.pacts.diff import DiffOutcome
from tingle.pacts.report import ERROR_STAT, UNGROUPED

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from tingle.pacts.metrics import Occurrence
    from tingle.pacts.report import GroupSummary, MetricOutcome


def metric_key(name: str) -> str:
    """Identify a metric row. Metric names are unique across a config."""
    return f"metric:{name}"


def group_key(name: str | None) -> str:
    """Identify a group row; `None` is the ungrouped section's own key."""
    return f"group:{name or ''}"


def start(outcomes: Sequence[MetricOutcome | DiffOutcome]) -> BrowseState:
    """Open a session over a finished report: every metric folded.

    Metrics start folded and groups start open, so the listing opens as an
    outline of what was measured rather than as every located hit at once.
    """
    return BrowseState(
        outcomes=tuple(outcomes),
        folded=frozenset(metric_key(outcome.spec.name) for outcome in outcomes),
    )


def push_sort(
    state: BrowseState, key: SortKey, *, descending: bool = False
) -> BrowseState:
    """Sort by `key`, keeping the previous sorts as tie-breakers.

    Sorting by name and then by type gives type-major order with names
    ordered inside each type -- the stack is what makes that work. A key
    already in the stack moves to the front rather than appearing twice,
    so asking for the same key the other way round turns the order over
    instead of stacking the key on itself.
    """
    step = Sort(key=key, descending=descending)
    return replace(state, sort=(step, *(s for s in state.sort if s.key is not key)))


def clear_sort(state: BrowseState) -> BrowseState:
    """Drop every sort, returning the rows to config order."""
    return replace(state, sort=())


def outlined(state: BrowseState) -> bool:
    """Whether the group outline -- and with it folding -- is available.

    Only while nothing is sorted, or while `group` is the sort the reader
    pushed last. Any other primary key orders metrics across the whole
    run, so they no longer nest under a group; the view flattens to one
    row per metric and there is nothing left to fold. Clearing the sort
    brings the outline, the folds and the occurrence rows back.
    """
    return not state.sort or state.sort[0].key is SortKey.GROUP


def grouped(state: BrowseState) -> bool:
    """Whether the run has groups at all, whatever the view is doing to them.

    Read off every outcome the session holds rather than the visible
    rows, so a search that spared only ungrouped metrics -- or a sort
    that flattened the outline -- does not make a grouped run look flat.
    """
    return any(outcome.spec.group is not None for outcome in state.outcomes)


def set_query(state: BrowseState, query: str) -> BrowseState:
    """Search for `query`, or leave search mode when it is empty.

    Fold gestures made during a search are part of the search: they last
    while the query does and are dropped with it, leaving the outline the
    reader built exactly as it was.
    """
    if not query:
        return replace(state, query="", overlay={})
    return replace(state, query=query)


def set_fold(state: BrowseState, key: str, *, folded: bool) -> BrowseState:
    """Fold or unfold one row.

    Whether a row is folded is answered by `rows`, which resolves it for
    every row in one pass; a caller acting on a row already holds that
    answer as `Row.folded` and passes back the other one.

    During a search the gesture is recorded apart from the fold set, so
    that leaving the search leaves the outline untouched.
    """
    if state.query:
        return replace(state, overlay={**state.overlay, key: folded})
    if folded:
        return replace(state, folded=state.folded | {key})
    return replace(state, folded=state.folded - {key})


def toggle_fold_all(state: BrowseState) -> BrowseState:
    """Fold every group at once, or unfold them all once none is unfolded.

    A run with no groups anywhere has metric rows at the top level, so
    there the metrics fold instead -- whatever the outline's top row is,
    that is what this collapses the listing to.
    """
    if not (top := _fold_all_rows(state)):
        return state
    folded = any(row.folded is False for row in top)
    for row in top:
        state = set_fold(state, row.key, folded=folded)
    return state


def fold_quiet_groups(state: BrowseState) -> BrowseState:
    """Fold away the groups a report has nothing to say about.

    A run's group is quiet when it measured nothing at all, a branch's
    when it moved nothing; either way it is noise beside the groups that
    did have something to report. A group holding an error is never
    quiet -- that is the one thing the reader most needs to see.

    A gesture rather than part of opening a session: a reader who folds
    everything away and then unfolds it should get their outline back,
    not this one.
    """
    quiet = frozenset(
        group_key(name)
        for name, section in _sections(_matches(state), state.sort)
        if _quiet(_section_summary(section))
    )
    return replace(state, folded=state.folded | quiet)


def rows(state: BrowseState) -> tuple[Row, ...]:
    """Every row that should be drawn, in the order it should be drawn.

    The one function the interactive gate renders; everything else here
    exists to answer it.
    """
    matches = _matches(state)
    if not outlined(state):
        return tuple(
            _metric_row(state, match, depth=0, foldable=False)
            for match in _sorted(matches, state.sort)
        )
    return tuple(_outline_rows(state, matches))


@dataclass(frozen=True)
class _Match:
    """One metric that survived the query, and what it may show.

    `occurrences` are the hits to show when the metric is unfolded: all
    of them normally, only the matching ones when the query found the
    metric through its files. `revealed` marks that second case, where
    the metric has to be opened or the reader is left with a row that
    gives no reason for being there.
    """

    outcome: MetricOutcome | DiffOutcome
    occurrences: tuple[Occurrence, ...]
    revealed: bool


def _matches(state: BrowseState) -> tuple[_Match, ...]:
    """Apply the query: which metrics are visible, showing which hits.

    Matching is case-sensitive substring, against everything a metric
    says about itself -- its name, its group, its description and the
    ranges it is measured over -- and against the path of every one of
    its occurrences, whether or not that occurrence is currently on
    screen. Nobody is going to unfold the whole tree before searching it.
    """
    if not state.query:
        return tuple(
            _Match(outcome, _occurrences(outcome), revealed=False)
            for outcome in state.outcomes
        )
    matches: list[_Match] = []
    for outcome in state.outcomes:
        occurrences = _occurrences(outcome)
        if _titled(outcome, state.query):
            matches.append(_Match(outcome, occurrences, revealed=False))
        elif _described(outcome, state.query):
            matches.append(_Match(outcome, occurrences, revealed=True))
        elif hits := tuple(o for o in occurrences if state.query in o.path):
            matches.append(_Match(outcome, hits, revealed=True))
    return tuple(matches)


def _titled(outcome: MetricOutcome | DiffOutcome, query: str) -> bool:
    """Whether the query matched text the metric's own row already shows.

    Its name and its group's are on screen the moment the metric is, so
    the row carries its own reason for being there and is left exactly as
    the reader had it.
    """
    return query in outcome.spec.name or query in (outcome.spec.group or "")


def _described(outcome: MetricOutcome | DiffOutcome, query: str) -> bool:
    """Whether the query matched what the metric says in its detail rows.

    A description or a range name is as much the metric's own word as its
    name is, but it is a row underneath rather than the row itself, so a
    metric found through one is opened to show it. Leaving it folded would
    give the reader a row with no visible reason for being there -- the
    very thing revealing a matched file avoids.
    """
    described = (outcome.spec.description or "", *outcome.range_names)
    return any(query in text for text in described)


def _occurrences(outcome: MetricOutcome | DiffOutcome) -> tuple[Occurrence, ...]:
    """Every hit a measured metric located; a diff's additions, then removals."""
    if outcome.result is None:
        return ()
    if isinstance(outcome, DiffOutcome):
        return (*outcome.result.added_occurrences, *outcome.result.removed_occurrences)
    return outcome.result.occurrences


def _outline_rows(state: BrowseState, matches: tuple[_Match, ...]) -> Iterable[Row]:
    """Group headers with their metrics, and their metrics' hits, nested."""
    has_groups = grouped(state)
    for name, section in _sections(matches, state.sort):
        depth, parent = 0, None
        if has_groups:
            key = group_key(name)
            # a search reveals every group holding something it found, or
            # the metric it found would stay hidden one level up
            folded = _folded(state, key, revealed=bool(state.query))
            yield _group_row(name, section, key=key, folded=folded)
            if folded:
                continue
            depth, parent = 1, key
        for match in section:
            yield from _metric_rows(state, match, depth=depth, parent=parent)


def _sections(
    matches: tuple[_Match, ...], sort: tuple[Sort, ...]
) -> list[tuple[str | None, list[_Match]]]:
    """Split the metrics into their groups, in the order to draw them.

    Config order by default, as everywhere else in tingle; by name when
    the reader sorted by group, and backwards when they asked for it that
    way. Either way the ungrouped section comes last -- it is a remainder,
    not a group with an empty name, so turning the order over does not
    lift it to the top.
    """
    sections: dict[str | None, list[_Match]] = {}
    for match in matches:
        sections.setdefault(match.outcome.spec.group, []).append(match)
    ungrouped = sections.pop(None, None)
    ordered: list[tuple[str | None, list[_Match]]] = list(sections.items())
    if sort and sort[0].key is SortKey.GROUP:
        ordered.sort(key=lambda section: section[0] or "", reverse=sort[0].descending)
    if ungrouped is not None:
        ordered.append((None, ungrouped))
    return [(name, _sorted(section, sort)) for name, section in ordered]


def _sorted(matches: Iterable[_Match], sort: tuple[Sort, ...]) -> list[_Match]:
    """Apply the sort stack, least significant key first.

    Python's sort is stable, so sorting by each key in turn from the
    bottom of the stack up leaves the most recently pushed key in charge
    and every earlier one deciding its ties. Name breaks whatever ties
    are left, so a sort is the same order twice running.
    """
    if not sort:
        return list(matches)
    ordered = sorted(matches, key=lambda match: match.outcome.spec.name)
    for step in reversed(sort):
        ordered = _sorted_by(ordered, step)
    return ordered


def _sorted_by(matches: list[_Match], step: Sort) -> list[_Match]:
    """Sort by one key, leaving what that key cannot place at the end.

    A metric that failed, or one in no group at all, has no position
    under the key being applied -- which is what its sorter returning
    None means. Those go last whichever way the sort runs, rather than
    counting as zero, which under `value` would rank them debt-free and
    under a reversed `value` would put them first.
    """
    sorter = _SORTERS[step.key]
    placed = [match for match in matches if sorter(match) is not None]
    unplaced = [match for match in matches if sorter(match) is None]
    placed.sort(key=sorter, reverse=step.descending)
    return [*placed, *unplaced]


#: What each key sorts a metric by, or None where it cannot place it.
_SORTERS: dict[SortKey, Callable[[_Match], Any]] = {
    SortKey.GROUP: lambda match: match.outcome.spec.group,
    SortKey.NAME: lambda match: match.outcome.spec.name,
    SortKey.TYPE: lambda match: match.outcome.spec.type,
    SortKey.VALUE: lambda match: _value(match.outcome),
    SortKey.SCORE: lambda match: _score(match.outcome),
}


def _value(outcome: MetricOutcome | DiffOutcome) -> int | None:
    """Return the number a metric measured, or None if it measured none.

    A diff's number is its standing total, not its net: a branch that
    moved nothing still sits on whatever debt was already there.
    """
    if isinstance(outcome, DiffOutcome):
        return outcome.total.value if outcome.total is not None else None
    return outcome.result.value if outcome.result is not None else None


def _score(outcome: MetricOutcome | DiffOutcome) -> float | None:
    """How bad a metric's value is against its own guide, or None."""
    if (value := _value(outcome)) is None:
        return None
    return severity_ratio(value, outcome.guide)


def _group_row(
    name: str | None, section: list[_Match], *, key: str, folded: bool
) -> Row:
    """Build a group header out of what its metrics add up to.

    The total is what has arrived so far and climbs as the run goes on:
    a partial sum says more than a blank, and blanking it until the last
    metric lands would leave the header saying nothing for the whole run.
    """
    return Row(
        kind=RowKind.GROUP,
        key=key,
        depth=0,
        cells=_group_cells(name, _section_summary(section)),
        folded=folded,
    )


def _section_summary(section: Sequence[_Match]) -> GroupSummary:
    """Add up what a group's metrics say -- the ones a query left, at that.

    Under a live query a group header totals only the metrics the query
    matched, which is the one place a section's sum is deliberately not
    the report's: it says what is on screen.
    """
    return group_summary(tuple(match.outcome for match in section))


def _quiet(summary: GroupSummary) -> bool:
    """Whether a group has nothing to report -- see `fold_quiet_groups`."""
    if summary.has_error:
        return False
    if summary.net is not None:
        return not summary.changed
    return summary.value == 0


def _metric_rows(
    state: BrowseState, match: _Match, *, depth: int, parent: str | None
) -> Iterable[Row]:
    """Draw a metric, then what it says about itself and what it found.

    The detail lines come before the hits: what a metric measures reads
    as an introduction to the list, not a footnote after it.
    """
    row = _metric_row(state, match, depth=depth, foldable=True, parent=parent)
    yield row
    if row.folded is not False:
        return
    for index, text in enumerate(_details(match.outcome)):
        yield Row(
            kind=RowKind.DETAIL,
            key=f"{row.key}/detail/{index}",
            depth=depth + 1,
            cells=(text, "", ""),
            parent=row.key,
            outcome=match.outcome,
        )
    for index, occurrence in enumerate(match.occurrences):
        yield Row(
            kind=RowKind.OCCURRENCE,
            key=f"{row.key}/{index}",
            depth=depth + 1,
            cells=(str(occurrence), "", ""),
            parent=row.key,
            outcome=match.outcome,
            occurrence=occurrence,
        )


def _details(outcome: MetricOutcome | DiffOutcome) -> tuple[str, ...]:
    """Gather what a metric says about itself: what, where, and why not.

    A metric that failed says so here rather than leaving the reader with
    an ERROR in the value column and nowhere to find out what happened.
    """
    lines = []
    if (description := outcome.spec.description) is not None:
        lines.append(description)
    if names := outcome.range_names:
        lines.append(f"ranges: {', '.join(names)}")
    if outcome.error is not None:
        lines.append(outcome.error)
    return tuple(lines)


def _metric_row(
    state: BrowseState,
    match: _Match,
    *,
    depth: int,
    foldable: bool,
    parent: str | None = None,
) -> Row:
    """One metric's own row. Nothing to fold means no fold state at all."""
    key = metric_key(match.outcome.spec.name)
    has_body = bool(match.occurrences) or bool(_details(match.outcome))
    folded = (
        _folded(state, key, revealed=match.revealed) if foldable and has_body else None
    )
    return Row(
        kind=RowKind.METRIC,
        key=key,
        depth=depth,
        cells=_metric_cells(match.outcome),
        folded=folded,
        parent=parent,
        outcome=match.outcome,
    )


def _group_cells(name: str | None, summary: GroupSummary) -> tuple[str, str, str]:
    label = name if name is not None else UNGROUPED
    stat = f"{summary.emoji} {summary.value}"
    if summary.net is not None:
        stat = f"net {summary.net:+d} of {stat}"
    return (label, "", stat)


def _metric_cells(outcome: MetricOutcome | DiffOutcome) -> tuple[str, str, str]:
    return (outcome.spec.name, outcome.spec.type, _stat(outcome))


def _stat(outcome: MetricOutcome | DiffOutcome) -> str:
    """Fill the value column with the number, led by the rank it earned.

    The rank is the one the mill decided when it resolved the guide, not
    a second opinion worked out here: two ladders that must agree are a
    drift waiting to happen, and this is the view that would win it.
    """
    if outcome.result is None:
        return ERROR_STAT
    if isinstance(outcome, DiffOutcome):
        return _diff_stat(outcome)
    return f"{outcome.emoji} {outcome.result.value}"


def _diff_stat(outcome: DiffOutcome) -> str:
    """Say what a branch did to a metric, beside where the metric now stands."""
    if (result := outcome.result) is None:  # pragma: no cover - caller guards
        return ERROR_STAT
    net = f"net {result.net:+d}"
    if outcome.total is None:
        return f"{net} of ?"
    standing = f"{net} of {outcome.emoji} {outcome.total.value}"
    if result.added is None or result.removed is None:
        return standing
    return f"+{result.added} / -{result.removed} ({standing})"


def _folded(state: BrowseState, key: str, *, revealed: bool) -> bool:
    """Resolve one row's fold state: overlay, then reveal, then fold set."""
    if not state.query:
        return key in state.folded
    if key in state.overlay:
        return state.overlay[key]
    return not revealed and key in state.folded


def _fold_all_rows(state: BrowseState) -> list[Row]:
    """Find the rows `fold all` acts on: the groups, or the metrics if none."""
    rendered = rows(state)
    if groups := [row for row in rendered if row.kind is RowKind.GROUP]:
        return groups
    return [
        row for row in rendered if row.kind is RowKind.METRIC and row.folded is not None
    ]
