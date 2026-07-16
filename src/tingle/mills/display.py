"""Turning measured numbers into what a reader sees: emoji and group sums.

The rules live here rather than in the gates so the TUI, the tables and
the listings cannot drift apart -- they are three views of one judgement.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from tingle.pacts.diff import DiffOutcome
from tingle.pacts.report import GroupSummary
from tingle.specs.display import EMOJI_BANDS, EMOJI_OVER, EMOJI_ZERO, LOC_PER_GUIDE

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from tingle.pacts.config import DisplaySpec, MetricSpec
    from tingle.pacts.report import MetricOutcome


def effective_guide(
    spec: MetricSpec, display: DisplaySpec, *, loc: Callable[[], int]
) -> int:
    """Return the guide a metric is judged against.

    Its own if it sets one; else the global `[display] guide` if that is
    pinned; else one derived from the size of the codebase, so the same
    seventy `noqa` comments mean different things in five thousand lines
    and in five hundred thousand.

    `loc` is a callable, not a number: counting the lines of a project
    means reading it, and a config that pins every guide must not pay for
    a pass nothing reads.
    """
    if spec.guide is not None:
        return spec.guide
    if display.guide is not None:
        return display.guide
    return loc_guide(loc())


def loc_guide(loc: int) -> int:
    """Derive a guide from the size of the codebase: one unit per N lines.

    Floored at 1, so an empty project still has something to divide by.
    """
    return max(1, round(loc / LOC_PER_GUIDE))


def severity_emoji(value: int, guide: int) -> str:
    """How bad `value` is against `guide`, as one emoji.

    The ratio is logarithmic: at `value == guide` it is exactly 1.0, as a
    linear ratio would be, so a guide keeps its meaning -- the point at
    which debt is full size. Below and above it the scale compresses,
    which is what spreads real metrics across the ladder instead of
    piling them on its bottom rung.

    Zero is answered before anything is divided, so a group whose metrics
    all errored -- no values, and so no guides to divide by -- is safe.
    """
    if value <= 0:
        return EMOJI_ZERO
    ratio = math.log1p(value) / math.log1p(max(guide, 1))
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
