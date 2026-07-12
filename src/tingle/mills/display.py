"""Turning measured numbers into what a reader sees: emoji and group sums.

The rules live here rather than in the gates so the TUI, the tables and
the listings cannot drift apart -- they are three views of one judgement.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tingle.pacts.diff import DiffOutcome
from tingle.pacts.report import GroupSummary
from tingle.specs.display import EMOJI_BANDS, EMOJI_OVER, EMOJI_ZERO

if TYPE_CHECKING:
    from collections.abc import Iterable

    from tingle.pacts.config import DisplaySpec, MetricSpec
    from tingle.pacts.report import MetricOutcome


def effective_guide(spec: MetricSpec, display: DisplaySpec) -> int:
    """Return the guide a metric is judged against: its own, or the global one."""
    return display.guide if spec.guide is None else spec.guide


def severity_emoji(value: int, guide: int) -> str:
    """How bad `value` is against `guide`, as one emoji.

    Zero is answered before anything is divided, so a group whose metrics
    all errored -- no values, and so no guides to divide by -- is safe.
    """
    if value <= 0:
        return EMOJI_ZERO
    ratio = value / guide
    for ceiling, emoji in EMOJI_BANDS:
        if ratio <= ceiling:
            return emoji
    return EMOJI_OVER


def group_summary(outcomes: Iterable[MetricOutcome | DiffOutcome]) -> GroupSummary:
    """Add a group's metrics up into the numbers its header shows.

    A diff's standing `value` is the sum of the metrics' current totals,
    not of their nets: a net of zero does not mean the debt is zero.
    """
    value = 0
    guide = 0
    net = 0
    has_error = False
    changed = False
    is_diff = False

    for outcome in outcomes:
        if outcome.result is None:
            has_error = True
            continue
        guide += outcome.guide
        if isinstance(outcome, DiffOutcome):
            is_diff = True
            net += outcome.result.net
            changed = changed or bool(
                outcome.result.net or outcome.result.added or outcome.result.removed
            )
            if outcome.total is not None:
                value += outcome.total.value
        else:
            value += outcome.result.value

    return GroupSummary(
        value=value,
        guide=guide,
        has_error=has_error,
        net=net if is_diff else None,
        changed=changed,
    )
