"""Contracts for browsing a run interactively: rows, sorting, state.

The interactive gate draws whatever `mills.browse` says is visible, so
the state of a browsing session -- which outcomes it is over, what is
folded, what is sorted, what is being searched for -- is a contract, not
a widget tree. Nothing here knows a terminal exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from tingle.pacts.diff import DiffOutcome
    from tingle.pacts.metrics import Occurrence
    from tingle.pacts.report import MetricOutcome


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
class BrowseState:
    """Everything a browsing session is, as data.

    `sort` is a stack, most recently pushed first, so consecutive sorts
    stack rather than replace each other. `folded` holds the keys of the
    groups and metrics the reader has folded; it survives sorting and
    searching untouched.

    `overlay` is the fold gestures made *during* a search, keyed the same
    way. A search reveals rows to show what it found, and an explicit
    fold beats that reveal -- but neither may outlive the query, so they
    are kept apart from `folded` and dropped when the query is cleared.
    """

    outcomes: tuple[MetricOutcome | DiffOutcome, ...] = ()
    sort: tuple[Sort, ...] = ()
    folded: frozenset[str] = frozenset()
    query: str = ""
    overlay: Mapping[str, bool] = field(default_factory=dict)
