from __future__ import annotations

import unicodedata

import pytest
from rich.cells import cell_len

from tingle.mills.display import effective_guide, group_summary, severity_emoji
from tingle.pacts.config import DEFAULT_GUIDE, DisplaySpec, MetricSpec
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


def test_effective_guide_prefers_the_metric_over_the_global() -> None:
    spec = MetricSpec(name="m", type="file_count", guide=5)

    assert effective_guide(spec, DisplaySpec(guide=100)) == 5


def test_effective_guide_falls_back_to_the_global() -> None:
    spec = MetricSpec(name="m", type="file_count")

    assert effective_guide(spec, DisplaySpec(guide=25)) == 25


def test_effective_guide_falls_back_to_the_default() -> None:
    spec = MetricSpec(name="m", type="file_count")

    assert effective_guide(spec, DisplaySpec()) == DEFAULT_GUIDE


@pytest.mark.parametrize(
    ("value", "emoji"),
    [
        (0, "🎉"),
        (1, "🦠"),
        (25, "🦠"),  # ratio 0.25 exactly: the band's ceiling is inclusive
        (26, "🚧"),
        (50, "🚧"),  # 0.50 exactly
        (51, "🚨"),
        (100, "🚨"),  # 1.00 exactly: at the guide, not yet past it
        (101, "🔥"),
        (200, "🔥"),  # 2.00 exactly
        (201, "💀"),  # past twice the guide
    ],
)
def test_severity_emoji_bands(value: int, emoji: str) -> None:
    assert severity_emoji(value, guide=100) == emoji


def test_severity_emoji_scales_with_the_guide() -> None:
    """The same value is judged differently against a tighter guide."""
    assert severity_emoji(10, guide=100) == "🦠"  # a tenth of the guide
    assert severity_emoji(10, guide=5) == "🔥"  # exactly twice it: still the last band
    assert severity_emoji(10, guide=4) == "💀"  # past twice it


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
