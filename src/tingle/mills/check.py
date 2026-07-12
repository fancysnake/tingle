"""Judging a branch diff against the configured check policy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tingle.pacts.check import CheckVerdict
from tingle.pacts.config import CheckPolicy

if TYPE_CHECKING:
    from tingle.pacts.config import CheckSpec
    from tingle.pacts.diff import DiffOutcome, DiffReport


def judge(report: DiffReport, spec: CheckSpec) -> CheckVerdict:
    """Decide whether the branch worsened the metrics it is judged on.

    Metrics named in `spec.ignore` take no part: they neither move the
    total nor fail the check. Metrics that errored are left to the caller
    to report — a metric that could not be measured is not evidence that
    the branch got better or worse.
    """
    judged: list[DiffOutcome] = [
        outcome
        for outcome in report.outcomes
        if outcome.spec.name not in spec.ignore and outcome.result is not None
    ]
    net_total = sum(outcome.result.net for outcome in judged if outcome.result)
    worsened = tuple(
        outcome for outcome in judged if outcome.result and outcome.result.net > 0
    )
    failed = net_total > 0 if spec.policy is CheckPolicy.SUM else bool(worsened)
    return CheckVerdict(
        policy=spec.policy,
        worsened=worsened,
        net_total=net_total,
        failed=failed,
        judged=len(judged),
    )
