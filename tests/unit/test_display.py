from __future__ import annotations

import unicodedata

import pytest
from rich.cells import cell_len

from tingle.mills.display import (
    effective_guide,
    group_summary,
    loc_guide,
    severity_emoji,
)
from tingle.pacts.config import DisplaySpec, MetricSpec
from tingle.pacts.diff import DiffOutcome, DiffResult
from tingle.pacts.metrics import MetricResult
from tingle.pacts.report import MetricOutcome
from tingle.specs.display import EMOJI_BANDS, EMOJI_OVER, EMOJI_ZERO


def _outcome(value: int, *, guide: int = 100) -> MetricOutcome:
    return MetricOutcome(
        spec=MetricSpec(name="m", type="file_count"),
        range_names=(),
        result=MetricResult(value=value),
        guide=guide,
    )


def _failed(*, guide: int = 100) -> MetricOutcome:
    return MetricOutcome(
        spec=MetricSpec(name="boom", type="file_count"),
        range_names=(),
        error="ValueError: boom",
        guide=guide,
    )


def _diff_outcome(
    net: int, *, total: int, added: int = 0, removed: int = 0, guide: int = 100
) -> DiffOutcome:
    return DiffOutcome(
        spec=MetricSpec(name="m", type="file_count"),
        range_names=(),
        result=DiffResult(net=net, added=added, removed=removed),
        total=MetricResult(value=total),
        guide=guide,
    )


def _never_counted() -> int:
    raise AssertionError(NOT_COUNTED)


NOT_COUNTED = "LOC was counted when no metric needed it"


def test_effective_guide_prefers_the_metric_over_the_global() -> None:
    spec = MetricSpec(name="m", type="file_count", guide=5)

    assert effective_guide(spec, DisplaySpec(guide=100), loc=_never_counted) == 5


def test_effective_guide_falls_back_to_the_pinned_global() -> None:
    spec = MetricSpec(name="m", type="file_count")

    assert effective_guide(spec, DisplaySpec(guide=25), loc=_never_counted) == 25


def test_effective_guide_derives_from_loc_when_nothing_is_pinned() -> None:
    """No guide anywhere: debt is judged as a density, one unit per 100 lines."""
    spec = MetricSpec(name="m", type="file_count")

    assert effective_guide(spec, DisplaySpec(), loc=lambda: 94_000) == 940


def test_a_pinned_guide_never_counts_the_lines() -> None:
    """Counting means reading the tree; a config that pins guides must not pay."""
    spec = MetricSpec(name="m", type="file_count", guide=5)

    effective_guide(spec, DisplaySpec(), loc=_never_counted)  # would raise


@pytest.mark.parametrize(
    ("loc", "guide"),
    [
        (94_000, 940),
        (10_131, 101),
        (49, 0 + 1),  # rounds to zero, floored at 1: nothing to divide by otherwise
        (0, 1),  # an empty project
    ],
)
def test_loc_guide_is_a_density_floored_at_one(loc: int, guide: int) -> None:
    assert loc_guide(loc) == guide


@pytest.mark.parametrize(
    ("value", "emoji"),
    [
        (0, "🎉"),  # not a band but a state
        (1, "🦠"),
        (3, "🚧"),  # log bites early: 3 of a guide of 100 is already a quarter up
        (100, "🚨"),  # value == guide: ratio exactly 1.0, as it was linearly
        (10_403, "💀"),  # about guide squared: ratio 2.0, past the last band
    ],
)
def test_severity_emoji_anchors(value: int, emoji: str) -> None:
    assert severity_emoji(value, guide=100) == emoji


@pytest.mark.parametrize("guide", [1, 5, 100, 940, 20_000])
def test_the_guide_is_always_the_top_of_the_siren_band(guide: int) -> None:
    """Whatever the guide, `value == guide` means full-size debt: 🚨, not past it."""
    assert severity_emoji(guide, guide=guide) == "🚨"
    assert severity_emoji(guide + 1, guide=guide) in {"🔥", "🚨"}


def test_the_bands_climb_with_the_value() -> None:
    """The ladder must never rank a bigger number below a smaller one."""
    order = ["🎉", "🦠", "🚧", "🚨", "🔥", "💀"]
    seen = [severity_emoji(v, guide=940) for v in (0, 1, 10, 100, 940, 10_000, 900_000)]

    assert [order.index(e) for e in seen] == sorted(order.index(e) for e in seen)


def test_severity_emoji_of_zero_never_divides() -> None:
    """A group whose metrics all errored sums no guides; zero must not divide."""
    assert severity_emoji(0, guide=0) == "🎉"


def test_group_summary_sums_values_and_guides() -> None:
    summary = group_summary([_outcome(3, guide=10), _outcome(7, guide=20)])

    assert summary.value == 10
    assert summary.guide == 30
    assert not summary.has_error
    assert summary.net is None


def test_group_summary_flags_an_error_and_excludes_it_from_the_sums() -> None:
    summary = group_summary([_outcome(4, guide=10), _failed(guide=99)])

    assert summary.value == 4
    assert summary.guide == 10  # the failed metric contributes no guide
    assert summary.has_error


def test_group_summary_of_an_empty_group() -> None:
    summary = group_summary([])

    assert summary.value == 0
    assert summary.guide == 0
    assert not summary.has_error


def test_group_summary_of_a_diff_totals_the_standing_debt_not_the_net() -> None:
    """A net of zero does not mean the debt is zero."""
    summary = group_summary(
        [
            _diff_outcome(net=0, total=40, added=2, removed=2),
            _diff_outcome(net=3, total=10, added=3),
        ]
    )

    assert summary.value == 50  # the totals
    assert summary.net == 3
    assert summary.changed


def test_group_summary_of_an_unchanged_diff_group() -> None:
    summary = group_summary([_diff_outcome(net=0, total=40)])

    assert summary.net == 0
    assert not summary.changed
    assert summary.value == 40


def test_group_summary_diff_counts_churn_as_changed() -> None:
    """Two added and two removed nets to zero, but the branch did move things."""
    summary = group_summary([_diff_outcome(net=0, total=9, added=2, removed=2)])

    assert summary.net == 0
    assert summary.changed


def test_every_emoji_on_the_ladder_is_a_wide_single_codepoint() -> None:
    """A terminal must draw each one in the two cells the width assumes.

    The warning sign (U+26A0 U+FE0F) was not: a text-default character wearing
    a variation selector, of neutral width, which terminals draw in one cell
    and so clip in half.
    """
    ladder = [EMOJI_ZERO, EMOJI_OVER, *(emoji for _ceiling, emoji in EMOJI_BANDS)]

    for emoji in ladder:
        assert len(emoji) == 1, f"{emoji!r} is more than one codepoint"
        assert unicodedata.east_asian_width(emoji) == "W", f"{emoji!r} is not wide"
        assert cell_len(emoji) == 2, f"{emoji!r} does not occupy two cells"


# The 94k-line project whose table motivated the log ladder. Under the old
# linear ratio against a fixed guide of 100, twenty-one of these twenty-six
# metrics read the same emoji -- a ladder that ranked nothing.
REAL_PROJECT_LOC = 94_000
REAL_PROJECT_VALUES = (
    15_590,  # metric legacy-loc
    483,  # metric wrong-assert
    328,  # metric mock-ANY
    203,  # metric request-di-uow
    111,  # metric type-object
    96,  # metric type-any
    70,  # metric noqa-comment
    45,  # metric inline-styles
    40,  # metric type-ignores
    26,  # metric inline-handlers
    24,  # metric pylint-comment
    22,  # metric pylint-disables
    18,  # metric ruff-per-file-ignores
    15,  # metric script-tags
    12,  # metric ruff-ignores
    8,  # metric context-data-not-typed
    7,  # metric mypy-overrides
    5,  # metric todo-comments
    4,  # metric mypy-strictness-holes
    3,  # metric template-filter-safe
    2,  # metric pytest-skip
    0,  # metric fmt-comment
)


def test_a_real_project_spreads_across_the_ladder() -> None:
    """The failure this scale exists to fix: every metric on one rung."""
    guide = loc_guide(REAL_PROJECT_LOC)
    rungs = {severity_emoji(value, guide) for value in REAL_PROJECT_VALUES}

    assert len(rungs) >= 4  # the 70-hit metric must not read like the 2-hit one


def test_a_real_project_keeps_the_worst_metric_alone_at_the_top() -> None:
    """15,590 lines of legacy code is not the same problem as 483 bad asserts."""
    guide = loc_guide(REAL_PROJECT_LOC)

    assert severity_emoji(15_590, guide) == "🔥"
    assert severity_emoji(483, guide) == "🚨"
    assert severity_emoji(2, guide) == "🦠"
    assert severity_emoji(0, guide) == "🎉"
