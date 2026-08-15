"""Contracts for browsing a run interactively: rows, sorting, state.

The interactive gate draws whatever `mills.browse` says is visible, so
the state of a browsing session -- which outcomes it is over, what is
folded, what is sorted, what is being searched for -- is a contract, not
a widget tree. Nothing here knows a terminal exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tingle.pacts.diff import DiffOutcome
    from tingle.pacts.metrics import Occurrence
    from tingle.pacts.report import MetricOutcome, ReportSection


class SortKey(StrEnum):
    """A column the reader can sort by.

    VALUE and SCORE are separate keys because they answer different
    questions: value is the raw count ("what is biggest"), score is the
    value against the metric's own guide ("what is worst"), which is the
    only one of the two that compares metrics with different guides.
    """

    GROUP = "group"
    NAME = "name"
    TYPE = "type"
    VALUE = "value"
    SCORE = "score"


class RowKind(StrEnum):
    """What a visible row stands for.

    One table holds all four, so a renderer reads this rather than
    guessing from which fields happen to be set.

    DETAIL is what a metric says about itself -- what it measures, over
    which ranges, and why it failed. It sits under the metric rather than
    beside it because the table has three columns and none of them is
    prose.
    """

    GROUP = "group"
    METRIC = "metric"
    DETAIL = "detail"
    OCCURRENCE = "occurrence"


@dataclass(frozen=True)
class Sort:
    """One key in the sort stack, and which way it runs.

    Direction is the reader's to choose rather than the key's: `v` asks
    for the biggest values and `V` for the smallest, and neither is more
    natural than the other once the question is theirs to ask.
    """

    key: SortKey
    descending: bool = False


@dataclass(frozen=True)
class Row:
    """One line of the browser, ready to be drawn.

    `cells` is the row's text for the Group/Metric, Type and Value
    columns, already carrying the emoji a value earns; occurrence and
    detail rows leave the last two blank, since neither a located hit nor
    a line of prose has a type or value of its own. Styling is the
    renderer's business, so no markup reaches here.

    `folded` is None on a row that cannot be folded -- an occurrence, a
    detail, or a metric with nothing under it -- which is not the same as
    False.

    `parent` is the key of the row this one folds into, None at the top
    level, so a renderer acting on a row can find what encloses it
    without knowing how a key is spelled.

    `outcome` and `occurrence` carry what the row was made from, so a
    renderer can act on a row (open a hit in the editor, colour a diff)
    without parsing its text back apart.
    """

    kind: RowKind
    key: str
    depth: int
    cells: tuple[str, str, str]
    folded: bool | None = None
    parent: str | None = None
    outcome: MetricOutcome | DiffOutcome | None = None
    occurrence: Occurrence | None = None


@dataclass(frozen=True)
class Search:
    """A live query, and the folds the reader made while it was up.

    A search reveals rows to show what it found, and an explicit fold
    beats that reveal -- but a gesture made inside a search may not
    outlive it, so it is held here rather than in the session's own fold
    set. Clearing the query drops the whole object, which is what makes
    that rule a shape rather than a branch someone has to remember.

    Folded and unfolded are two sets rather than one mapping so that
    every field of a frozen state is as frozen as the dataclass says it
    is; `with_fold` is the only writer, and it keeps them apart.
    """

    query: str
    folded: frozenset[str] = frozenset()
    unfolded: frozenset[str] = frozenset()

    def with_fold(self, key: str, *, folded: bool) -> Search:
        """Record one gesture, replacing whatever this search said before."""
        if folded:
            return Search(
                query=self.query,
                folded=self.folded | {key},
                unfolded=self.unfolded - {key},
            )
        return Search(
            query=self.query, folded=self.folded - {key}, unfolded=self.unfolded | {key}
        )

    def gesture(self, key: str) -> bool | None:
        """Whether the reader folded this row during the search, if they did."""
        if key in self.folded:
            return True
        if key in self.unfolded:
            return False
        return None


@dataclass(frozen=True)
class BrowseState:
    """Everything a browsing session is, as data.

    `sections` is the report's own grouping, kept as the report handed it
    over: the session reorders and filters it, and never works out which
    group a metric belongs to a second time.

    `sort` is a stack, most recently pushed first, so consecutive sorts
    stack rather than replace each other. `folded` holds the keys of the
    groups and metrics the reader has folded; it survives sorting and
    searching untouched.

    `search` is None when no query is up, which is the only way to say it.
    """

    sections: tuple[ReportSection[MetricOutcome | DiffOutcome], ...] = ()
    sort: tuple[Sort, ...] = ()
    folded: frozenset[str] = frozenset()
    search: Search | None = None

    @property
    def outcomes(self) -> tuple[MetricOutcome | DiffOutcome, ...]:
        """Every outcome the session is over, in the order sections hold them."""
        return tuple(
            outcome for section in self.sections for outcome in section.outcomes
        )
