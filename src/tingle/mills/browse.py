"""Browsing a run: what is visible, in what order, as results arrive.

One question is answered here -- given the outcomes so far, the sort
stack, the search query and the fold set, which rows should be drawn --
so that the interactive gate holds no view logic of its own and can be
tested without a terminal.

Every function is pure: `BrowseState` goes in, a new `BrowseState` or a
list of rows comes out. Nothing here reads a file, runs a metric, or
knows what a widget is.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from tingle.mills.display import group_summary, severity_emoji, severity_ratio
from tingle.pacts.browse import (
    BrowseState,
    MetricEntry,
    MetricStatus,
    Row,
    RowKind,
    SortKey,
)
from tingle.pacts.diff import DiffOutcome

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from tingle.pacts.config import MetricSpec
    from tingle.pacts.metrics import Occurrence
    from tingle.pacts.report import GroupSummary, MetricOutcome

#: What the section holding metrics with no group of their own is called.
UNGROUPED = "(ungrouped)"

#: Shown in the value column while a metric is being measured.
RUNNING_STAT = "…"

#: Shown in the value column of a metric that could not be measured.
ERROR_STAT = "ERROR"


def metric_key(name: str) -> str:
    """Identify a metric row. Metric names are unique across a config."""
    return f"metric:{name}"


def group_key(name: str | None) -> str:
    """Identify a group row; `None` is the ungrouped section's own key."""
    return f"group:{name or ''}"


def start(specs: Sequence[MetricSpec]) -> BrowseState:
    """Open a session over `specs`: every metric pending, and folded.

    The rows exist before the run does, which is the point: the reader
    sees the shape of what is about to happen instead of a blank screen.

    Metrics start folded and groups start open, so the listing opens as
    an outline of what is being measured rather than as every located hit
    at once. A group cannot start folded on how little it holds, the way
    a finished report's could: at this point it holds nothing, and folding
    a group away just as it begins to fill is the opposite of the point.
    """
    return BrowseState(
        entries=tuple(MetricEntry(spec=spec) for spec in specs),
        folded=frozenset(metric_key(spec.name) for spec in specs),
    )


def begin(state: BrowseState, name: str) -> BrowseState:
    """Mark one metric as being measured right now."""
    return _replace_entry(
        state, name, change=lambda entry: replace(entry, status=MetricStatus.RUNNING)
    )


def record(state: BrowseState, outcome: MetricOutcome | DiffOutcome) -> BrowseState:
    """Take one measured metric into the state.

    An outcome carrying no result is an error, and says so on its row;
    the run itself carries on, as it does everywhere else.
    """
    status = MetricStatus.DONE if outcome.result is not None else MetricStatus.ERROR
    return _replace_entry(
        state,
        outcome.spec.name,
        change=lambda entry: replace(entry, status=status, outcome=outcome),
    )


def restart(state: BrowseState) -> BrowseState:
    """Send every metric back to pending, keeping sort, folds and query.

    A re-run answers the same question again; it is not a reason to lose
    the reader's place in the outline.
    """
    return replace(
        state, entries=tuple(MetricEntry(spec=entry.spec) for entry in state.entries)
    )


def push_sort(state: BrowseState, key: SortKey) -> BrowseState:
    """Sort by `key`, keeping the previous sorts as tie-breakers.

    Sorting by name and then by type gives type-major order with names
    ordered inside each type -- the stack is what makes that work. A key
    already in the stack moves to the front rather than appearing twice.
    """
    return replace(state, sort=(key, *(k for k in state.sort if k is not key)))


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
    return not state.sort or state.sort[0] is SortKey.GROUP


def set_query(state: BrowseState, query: str) -> BrowseState:
    """Search for `query`, or leave search mode when it is empty.

    Fold gestures made during a search are part of the search: they last
    while the query does and are dropped with it, leaving the outline the
    reader built exactly as it was.
    """
    if not query:
        return replace(state, query="", overlay={})
    return replace(state, query=query)


def is_folded(state: BrowseState, key: str) -> bool:
    """Whether the row `key` is folded as things currently stand.

    Outside a search this is just the fold set. Inside one, a search may
    reveal a row to show what it found, and an explicit fold beats that
    reveal -- an outright gesture outranks something the query did on the
    reader's behalf.

    This answers one key at a time and derives the search matches to do
    it, so a renderer drawing a listing should read `Row.folded`, which
    `rows` has already resolved for every row in a single pass.
    """
    return _folded(state, key, revealed=_revealed(state, key))


def set_fold(state: BrowseState, key: str, *, folded: bool) -> BrowseState:
    """Fold or unfold one row.

    During a search the gesture is recorded apart from the fold set, so
    that leaving the search leaves the outline untouched.
    """
    if state.query:
        return replace(state, overlay={**state.overlay, key: folded})
    if folded:
        return replace(state, folded=state.folded | {key})
    return replace(state, folded=state.folded - {key})


def toggle_fold(state: BrowseState, key: str) -> BrowseState:
    """Fold an unfolded row, unfold a folded one."""
    return set_fold(state, key, folded=not is_folded(state, key))


def toggle_fold_all(state: BrowseState) -> BrowseState:
    """Fold every group at once, or unfold them all once none is unfolded.

    A run with no groups anywhere has metric rows at the top level, so
    there the metrics fold instead -- whatever the outline's top row is,
    that is what this collapses the listing to.

    The rows are read for their fold state rather than asked for it again:
    `is_folded` re-derives the search matches on every call, so resolving
    one key at a time would rescan every occurrence once per top row.
    """
    if not (top := _fold_all_rows(state)):
        return state
    folded = any(row.folded is False for row in top)
    for row in top:
        state = set_fold(state, row.key, folded=folded)
    return state


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

    entry: MetricEntry
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
            _Match(entry, _occurrences(entry), revealed=False)
            for entry in state.entries
        )
    matches: list[_Match] = []
    for entry in state.entries:
        occurrences = _occurrences(entry)
        if _named(entry, state.query):
            matches.append(_Match(entry, occurrences, revealed=False))
        elif hits := tuple(o for o in occurrences if state.query in o.path):
            matches.append(_Match(entry, hits, revealed=True))
    return tuple(matches)


def _named(entry: MetricEntry, query: str) -> bool:
    """Whether the query matched the metric itself, not a file underneath it.

    A metric's own name, its group's, its description and its range
    names all describe the metric rather than locate anything inside it,
    so a match on any of them leaves the metric exactly as the reader
    had it. There is nothing underneath to single out.
    """
    spec = entry.spec
    described = (spec.name, spec.group or "", spec.description or "")
    return any(query in text for text in (*described, *_range_names(entry)))


def _range_names(entry: MetricEntry) -> tuple[str, ...]:
    """Name the ranges a metric covers, as resolved once it has been measured.

    Before that only what the config named is known, which is nothing at
    all for a metric that leaves the default range implied -- so the
    default range becomes searchable when the metric's outcome lands.
    """
    if entry.outcome is not None:
        return entry.outcome.range_names
    return entry.spec.ranges


def _occurrences(entry: MetricEntry) -> tuple[Occurrence, ...]:
    """Every hit a measured metric located; a diff's additions, then removals."""
    outcome = entry.outcome
    if outcome is None or outcome.result is None:
        return ()
    if isinstance(outcome, DiffOutcome):
        return (*outcome.result.added_occurrences, *outcome.result.removed_occurrences)
    return outcome.result.occurrences


def _outline_rows(state: BrowseState, matches: tuple[_Match, ...]) -> Iterable[Row]:
    """Group headers with their metrics, and their metrics' hits, nested."""
    # whether the run has groups at all, not whether the query left any: a
    # search must not restyle the rows it spared into a different outline
    grouped = any(entry.spec.group is not None for entry in state.entries)
    for name, section in _sections(matches, state.sort):
        depth = 0
        if grouped:
            key = group_key(name)
            # a search reveals every group holding something it found, or
            # the metric it found would stay hidden one level up
            folded = _folded(state, key, revealed=bool(state.query))
            yield _group_row(name, section, key=key, folded=folded)
            if folded:
                continue
            depth = 1
        for match in section:
            yield from _metric_rows(state, match, depth=depth)


def _sections(
    matches: tuple[_Match, ...], sort: tuple[SortKey, ...]
) -> list[tuple[str | None, list[_Match]]]:
    """Split the metrics into their groups, in the order to draw them.

    Config order by default, as everywhere else in tingle; alphabetical
    when the reader sorted by group. Either way the ungrouped section
    comes last -- it is a remainder, not a group with an empty name.
    """
    sections: dict[str | None, list[_Match]] = {}
    for match in matches:
        sections.setdefault(match.entry.spec.group, []).append(match)
    ungrouped = sections.pop(None, None)
    ordered: list[tuple[str | None, list[_Match]]] = list(sections.items())
    if sort and sort[0] is SortKey.GROUP:
        ordered.sort(key=lambda section: section[0] or "")
    if ungrouped is not None:
        ordered.append((None, ungrouped))
    return [(name, _sorted(section, sort)) for name, section in ordered]


def _sorted(matches: Iterable[_Match], sort: tuple[SortKey, ...]) -> list[_Match]:
    """Apply the sort stack, least significant key first.

    Python's sort is stable, so sorting by each key in turn from the
    bottom of the stack up leaves the most recently pushed key in charge
    and every earlier one deciding its ties. Metrics the sort cannot
    place -- nothing measured yet, or a metric that failed -- go last
    rather than counting as zero, which would rank them as debt-free.
    """
    ordered = list(matches)
    for key in reversed(sort):
        ordered.sort(key=_SORTERS[key])
    return ordered


def _group_sort(match: _Match) -> tuple[bool, float, str]:
    group = match.entry.spec.group
    return (group is None, 0.0, group or "")


def _name_sort(match: _Match) -> tuple[bool, float, str]:
    return (False, 0.0, match.entry.spec.name)


def _type_sort(match: _Match) -> tuple[bool, float, str]:
    return (False, 0.0, match.entry.spec.type)


def _value_sort(match: _Match) -> tuple[bool, float, str]:
    """Biggest first: the question is what is largest, not what is smallest."""
    value = _value(match.entry)
    return (value is None, -float(value or 0), match.entry.spec.name)


def _score_sort(match: _Match) -> tuple[bool, float, str]:
    """Worst first, against each metric's own guide rather than its raw size."""
    score = _score(match.entry)
    return (score is None, -(score or 0.0), match.entry.spec.name)


_SORTERS: dict[SortKey, Callable[[_Match], tuple[bool, float, str]]] = {
    SortKey.GROUP: _group_sort,
    SortKey.NAME: _name_sort,
    SortKey.TYPE: _type_sort,
    SortKey.VALUE: _value_sort,
    SortKey.SCORE: _score_sort,
}


def _value(entry: MetricEntry) -> int | None:
    """Return the number a metric measured, or None while it has none.

    A diff's number is its standing total, not its net: a branch that
    moved nothing still sits on whatever debt was already there.
    """
    if (outcome := entry.outcome) is None:
        return None
    if isinstance(outcome, DiffOutcome):
        return outcome.total.value if outcome.total is not None else None
    return outcome.result.value if outcome.result is not None else None


def _score(entry: MetricEntry) -> float | None:
    """How bad a metric's value is against its own guide, or None."""
    if (value := _value(entry)) is None or entry.outcome is None:
        return None
    return severity_ratio(value, entry.outcome.guide)


def _group_row(
    name: str | None, section: list[_Match], *, key: str, folded: bool
) -> Row:
    """Build a group header out of what its metrics add up to.

    The total is what has arrived so far and climbs as the run goes on:
    a partial sum says more than a blank, and blanking it until the last
    metric lands would leave the header saying nothing for the whole run.
    """
    outcomes = tuple(
        match.entry.outcome for match in section if match.entry.outcome is not None
    )
    summary = group_summary(outcomes)
    return Row(
        kind=RowKind.GROUP,
        key=key,
        depth=0,
        cells=_group_cells(name, summary),
        folded=folded,
        summary=summary,
    )


def _metric_rows(state: BrowseState, match: _Match, *, depth: int) -> Iterable[Row]:
    """Draw a metric, and the hits underneath it when it is unfolded."""
    row = _metric_row(state, match, depth=depth, foldable=True)
    yield row
    if row.folded is False:
        for index, occurrence in enumerate(match.occurrences):
            yield Row(
                kind=RowKind.OCCURRENCE,
                key=f"{row.key}/{index}",
                depth=depth + 1,
                cells=(str(occurrence), "", ""),
                entry=match.entry,
                occurrence=occurrence,
            )


def _metric_row(
    state: BrowseState, match: _Match, *, depth: int, foldable: bool
) -> Row:
    """One metric's own row. Nothing to fold means no fold state at all."""
    key = metric_key(match.entry.spec.name)
    folded = (
        _folded(state, key, revealed=match.revealed)
        if foldable and match.occurrences
        else None
    )
    return Row(
        kind=RowKind.METRIC,
        key=key,
        depth=depth,
        cells=_metric_cells(match.entry),
        folded=folded,
        entry=match.entry,
    )


def _group_cells(name: str | None, summary: GroupSummary) -> tuple[str, str, str]:
    label = name if name is not None else UNGROUPED
    stat = _valued(summary.value, summary.guide)
    if summary.net is not None:
        stat = f"net {summary.net:+d} of {stat}"
    return (label, "", stat)


def _metric_cells(entry: MetricEntry) -> tuple[str, str, str]:
    return (entry.spec.name, entry.spec.type, _stat(entry))


def _stat(entry: MetricEntry) -> str:
    """Fill the value column: blank while pending, then the measured number."""
    if entry.status is MetricStatus.PENDING:
        return ""
    if entry.status is MetricStatus.RUNNING:
        return RUNNING_STAT
    outcome = entry.outcome
    if outcome is None or outcome.result is None:
        return ERROR_STAT
    if isinstance(outcome, DiffOutcome):
        return _diff_stat(outcome)
    return _valued(outcome.result.value, outcome.guide)


def _diff_stat(outcome: DiffOutcome) -> str:
    """Say what a branch did to a metric, beside where the metric now stands."""
    if (result := outcome.result) is None:  # pragma: no cover - caller guards
        return ERROR_STAT
    net = f"net {result.net:+d}"
    if outcome.total is None:
        return f"{net} of ?"
    standing = f"{net} of {_valued(outcome.total.value, outcome.guide)}"
    if result.added is None or result.removed is None:
        return standing
    return f"+{result.added} / -{result.removed} ({standing})"


def _valued(value: int, guide: int) -> str:
    return f"{severity_emoji(value, guide)} {value}"


def _folded(state: BrowseState, key: str, *, revealed: bool) -> bool:
    """Resolve one row's fold state: overlay, then reveal, then fold set."""
    if not state.query:
        return key in state.folded
    if key in state.overlay:
        return state.overlay[key]
    return not revealed and key in state.folded


def _revealed(state: BrowseState, key: str) -> bool:
    """Whether the current query is holding this row open."""
    if not state.query:
        return False
    matches = _matches(state)
    if any(group_key(match.entry.spec.group) == key for match in matches):
        return True
    return any(
        metric_key(match.entry.spec.name) == key and match.revealed for match in matches
    )


def _fold_all_rows(state: BrowseState) -> list[Row]:
    """Find the rows `fold all` acts on: the groups, or the metrics if none."""
    rendered = rows(state)
    if groups := [row for row in rendered if row.kind is RowKind.GROUP]:
        return groups
    return [
        row for row in rendered if row.kind is RowKind.METRIC and row.folded is not None
    ]


def _replace_entry(
    state: BrowseState, name: str, *, change: Callable[[MetricEntry], MetricEntry]
) -> BrowseState:
    """Apply `change` to the entry called `name`, leaving the rest alone."""
    return replace(
        state,
        entries=tuple(
            change(entry) if entry.spec.name == name else entry
            for entry in state.entries
        ),
    )
