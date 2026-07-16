"""Contracts for the CI gate (`tingle check`)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tingle.pacts.config import CheckPolicy
    from tingle.pacts.diff import DiffOutcome


@dataclass(frozen=True)
class CheckVerdict:
    """Whether the branch may land, and what argues against it.

    `worsened` holds every judged metric the branch grew, whatever the
    policy decided — under SUM a branch can carry a worsened metric and
    still pass, and those occurrences are still worth showing.

    `judged` counts the metrics that took part, which is what a passing
    check reports: "nothing grew" means little without saying of how many.
    """

    policy: CheckPolicy
    worsened: tuple[DiffOutcome, ...]
    net_total: int
    failed: bool
    judged: int = 0
