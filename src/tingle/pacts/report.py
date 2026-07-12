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
