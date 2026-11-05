"""Contracts for the CI gate (`tingle check`)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import PurePath

    from tingle.pacts.config import CheckPolicy
    from tingle.pacts.diff import DiffOutcome


@dataclass(frozen=True)
class Loosening:
    """One way the branch's config weakens the gate its base set up."""

    subject: str
    change: str


@dataclass(frozen=True)
class StrictVerdict:
    """What `[check] strict` found: loosening, and what rode along with it.

    `skipped` says why strict mode could not judge the branch, when the
    base asked for it or the branch does.
    """

    loosened: tuple[Loosening, ...] = ()
    alongside: tuple[PurePath, ...] = ()
    skipped: str | None = None

    @property
    def failed(self) -> bool:
        """Whether loosening shares the branch with anything else."""
        return bool(self.loosened and self.alongside)


@dataclass(frozen=True)
class CheckVerdict:
    """Whether the branch may land, and what argues against it.

    `worsened` holds every judged metric the branch grew, whatever the
    policy decided — under SUM a branch can carry a worsened metric and
    still pass, and those occurrences are still worth showing.

    `judged` counts the metrics that took part, which is what a passing
    check reports: "nothing grew" means little without saying of how many.

    `failed` is the policy's answer alone; `rejected` is the whole verdict.
    """

    policy: CheckPolicy
    worsened: tuple[DiffOutcome, ...]
    net_total: int
    failed: bool
    judged: int = 0
    strict: StrictVerdict = field(default_factory=StrictVerdict)

    @property
    def rejected(self) -> bool:
        """Whether the branch may not land, on debt or on loosening."""
        return self.failed or self.strict.failed
