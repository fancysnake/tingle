"""Contracts describing the outcome of a run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from tingle.pacts.config import MetricSpec
    from tingle.pacts.metrics import MetricResult


@dataclass(frozen=True)
class MetricOutcome:
    """Result of one metric: either a MetricResult or an error message."""

    spec: MetricSpec
    range_names: tuple[str, ...]
    result: MetricResult | None = None
    error: str | None = None


@dataclass(frozen=True)
class RunReport:
    """The outcome of one tingle run over every selected metric."""

    root: Path
    source: Path
    outcomes: tuple[MetricOutcome, ...]
