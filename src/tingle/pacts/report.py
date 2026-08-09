"""Contracts describing the outcome of a run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar

from tingle.pacts.config import DEFAULT_GUIDE

if TYPE_CHECKING:
    from pathlib import Path

    from tingle.pacts.config import MetricSpec
    from tingle.pacts.diff import DiffOutcome
    from tingle.pacts.metrics import MetricResult


@dataclass(frozen=True)
class MetricOutcome:
    """Result of one metric: either a MetricResult or an error message.

    `guide` is already resolved: the metric's own, or the one from
    `[display]`. Renderers read it as-is and never redo the fallback.

    `emoji` is how bad the measured value is against that guide, decided
    where the guide was, so that every view of a run shows one judgement
    rather than each recomputing its own. It has no default: empty means
    an errored outcome with no value to rank, and a producer that forgot
    would otherwise say the same thing without meaning it.
    """

    spec: MetricSpec
    range_names: tuple[str, ...]
    emoji: str
    result: MetricResult | None = None
    error: str | None = None
    guide: int = DEFAULT_GUIDE


_Outcome = TypeVar("_Outcome", bound="MetricOutcome | DiffOutcome")


@dataclass(frozen=True)
class ReportSection(Generic[_Outcome]):
    """One group of a report's outcomes, and what they add up to.

    `name` is None for the metrics belonging to no group, whose section is
    always last. Sections come pre-summed because grouping and summing are
    the same judgement the emoji are: a renderer walks them, it does not
    work them out.
    """

    name: str | None
    outcomes: tuple[_Outcome, ...]
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

    `net` and `changed` describe a branch and stay None/False for a run.
    `emoji` has no default, for the reason MetricOutcome's has none.
    """

    value: int
    guide: int
    emoji: str
    has_error: bool = False
    net: int | None = None
    changed: bool = False
