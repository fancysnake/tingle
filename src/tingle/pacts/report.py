"""Contracts describing the outcome of a run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tingle.pacts.config import DEFAULT_GUIDE

if TYPE_CHECKING:
    from pathlib import Path

    from tingle.pacts.config import MetricSpec
    from tingle.pacts.metrics import MetricResult


@dataclass(frozen=True)
class MetricOutcome:
    """Result of one metric: either a MetricResult or an error message.

    `guide` is already resolved: the metric's own, or the one from
    `[display]`. Renderers read it as-is and never redo the fallback.
    """

    spec: MetricSpec
    range_names: tuple[str, ...]
    result: MetricResult | None = None
    error: str | None = None
    guide: int = DEFAULT_GUIDE


@dataclass(frozen=True)
class RunReport:
    """The outcome of one tingle run over every selected metric."""

    root: Path
    source: Path
    outcomes: tuple[MetricOutcome, ...]


@dataclass(frozen=True)
class GroupSummary:
    """What a group of metrics adds up to, for its header.

    `value` is the group's standing debt and `guide` the sum of the guides
    it is judged against, so a group takes its emoji off the same ladder a
    metric does. Errored metrics add to neither -- there is no number to
    add -- but they do raise `has_error`, which keeps a group holding an
    error from being folded away.

    `net` and `changed` describe a branch and stay None/False for a run.
    """

    value: int
    guide: int
    has_error: bool = False
    net: int | None = None
    changed: bool = False
