"""Contracts describing the outcome of a run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, Self, TypeVar

from tingle.pacts.config import DEFAULT_GUIDE

if TYPE_CHECKING:
    from pathlib import Path

    from tingle.pacts.config import MetricSpec
    from tingle.pacts.diff import DiffOutcome
    from tingle.pacts.metrics import MetricResult

#: What the section holding the metrics with no group of their own is
#: called. The static table and the interactive one both name it, and a
#: word two views must agree on is a contract rather than either's own.
UNGROUPED = "(ungrouped)"

#: Shown in place of the value of a metric that could not be measured.
ERROR_STAT = "ERROR"

#: Shown in place of a standing total nobody could work out -- a diff whose
#: metric errored on the full tree, or a group holding one.
UNKNOWN_STAT = "?"


def stat_text(emoji: str, value: int | None, *, width: int = 0) -> str:
    """Render a measured number, led by the rank the mill gave it.

    Both views of a run compose this, so the sentence is a contract for the
    same reason the emoji in it is one: a number that reads differently in
    the table and in the browser is the drift the shared rank was meant to
    close, moved one layer along.

    `width` right-pads the number with spaces so that, down a column, every
    emoji lands in the same place and the digits line up under each other.
    A value of None is a total that could not be worked out, which ranks as
    nothing and reads as such.
    """
    if value is None:
        return UNKNOWN_STAT
    return f"{emoji} {value:>{width}}"


def net_text(net: int) -> str:
    """Render what a branch did to a metric, sign and all."""
    return f"net {net:+d}"


@dataclass(frozen=True)
class MeasuredOutcome:
    """What a run and a diff say about one metric in common.

    `guide` is already resolved: the metric's own, or the one from
    `[display]`. Renderers read it as-is and never redo the fallback.

    `emoji` is how bad the measured value is against that guide, decided
    where the guide was, so that every view of a run shows one judgement
    rather than each recomputing its own. It has no default: empty means
    an errored outcome with no value to rank, and a producer that forgot
    would otherwise say the same thing without meaning it.

    What the two kinds measure differs and is theirs alone; that a metric
    was asked, and what it said if it could not answer, is shared -- so it
    is stated once, here, rather than agreed twice.
    """

    spec: MetricSpec
    range_names: tuple[str, ...]
    emoji: str
    error: str | None = None
    guide: int = DEFAULT_GUIDE

    @classmethod
    def errored(
        cls,
        spec: MetricSpec,
        *,
        range_names: tuple[str, ...],
        guide: int,
        exc: Exception,
    ) -> Self:
        """Report a metric that raised: the reason kept, and nothing ranked.

        A run and a diff isolate their metrics the same way and say the
        same thing about one that failed; only the kind of outcome they
        hand back differs, which is what `cls` is.
        """
        return cls(
            spec=spec,
            range_names=range_names,
            emoji="",
            error=f"{type(exc).__name__}: {exc}",
            guide=guide,
        )


@dataclass(frozen=True)
class MetricOutcome(MeasuredOutcome):
    """Result of one metric: either a MetricResult or an error message."""

    result: MetricResult | None = None


#: Covariant because a section is frozen and only ever read out of: a
#: browsing session holds the sections of either kind of report, and a
#: run's sections have to pass as sections of outcomes in general.
_Outcome_co = TypeVar(
    "_Outcome_co", bound="MetricOutcome | DiffOutcome", covariant=True
)


@dataclass(frozen=True)
class ReportSection(Generic[_Outcome_co]):
    """One group of a report's outcomes, and what they add up to.

    `name` is None for the metrics belonging to no group, whose section is
    always last. Sections come pre-summed because grouping and summing are
    the same judgement the emoji are: a renderer walks them, it does not
    work them out.
    """

    name: str | None
    outcomes: tuple[_Outcome_co, ...]
    summary: GroupSummary


@dataclass(frozen=True)
class RunReport:
    """The outcome of one tingle run over every selected metric.

    Sections are the only storage: `outcomes` is the same fact flattened,
    so the two cannot disagree and no construction site can hand over a
    report that renders as an empty table.
    """

    root: Path
    source: Path
    sections: tuple[ReportSection[MetricOutcome], ...]

    @property
    def outcomes(self) -> tuple[MetricOutcome, ...]:
        """Every outcome the run produced, in the order sections draw them."""
        return tuple(
            outcome for section in self.sections for outcome in section.outcomes
        )


@dataclass(frozen=True)
class GroupSummary:
    """What a group of metrics adds up to, for its header.

    `value` is the group's standing debt and `guide` the sum of the guides
    it is judged against, so a group takes its emoji off the same ladder a
    metric does. Errored metrics add to neither -- there is no number to
    add -- but they do raise `has_error`, which keeps a group holding an
    error from being folded away.

    `value` is None when a member's standing total could not be worked out
    at all: the group's debt is then unknown rather than the sum of the
    ones that did land, which would read as a smaller debt than there is.
    Nothing unknown can be ranked, so `emoji` is empty alongside it.

    `net` and `changed` describe a branch and stay None/False for a run.
    `emoji` has no default, for the reason MetricOutcome's has none.
    """

    value: int | None
    guide: int
    emoji: str
    has_error: bool = False
    net: int | None = None
    changed: bool = False
