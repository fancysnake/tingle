from __future__ import annotations

from typing import TYPE_CHECKING

from tingle.mills import browse
from tingle.mills.browse import (
    clear_sort,
    fold_quiet_groups,
    group_key,
    grouped,
    metric_key,
    outlined,
    push_sort,
    rows,
    set_fold,
    set_query,
    toggle_fold_all,
)
from tingle.mills.display import outcome_emoji, sections
from tingle.pacts.browse import BrowseState, RowKind, Sort, SortKey
from tingle.pacts.config import MetricSpec
from tingle.pacts.diff import DiffOutcome, DiffResult
from tingle.pacts.metrics import MetricResult, Occurrence
from tingle.pacts.report import UNGROUPED, MetricOutcome

if TYPE_CHECKING:
    from collections.abc import Sequence


def start(outcomes: Sequence[MetricOutcome | DiffOutcome]) -> BrowseState:
    """Open a session the way a gate does: over the report's own sections.

    Grouping is the report's, so a session is started from what it built
    rather than from a bare tuple no report would hand over.
    """
    return browse.start(sections(tuple(outcomes)))


NOQA = MetricSpec(name="noqa-comment", type="regex_count", group="linting")
PYLINT = MetricSpec(name="pylint-comment", type="regex_count", group="linting")
LOC = MetricSpec(name="loc", type="file_lines", group="size")
LEGACY = MetricSpec(name="legacy-arch", type="symbol_uses")


def _outcome(
    spec: MetricSpec, value: int, *, guide: int = 100, paths: tuple[str, ...] = ()
) -> MetricOutcome:
    result = MetricResult(
        value=value, occurrences=tuple(Occurrence(path=path, line=1) for path in paths)
    )
    return MetricOutcome(
        spec=spec,
        range_names=("src",),
        emoji=outcome_emoji(result, guide),
        result=result,
        guide=guide,
    )


def _failed(spec: MetricSpec, *, ranges: tuple[str, ...] = ()) -> MetricOutcome:
    """One metric that raised: no result, and so nothing ranked."""
    return MetricOutcome(
        spec=spec, range_names=ranges, emoji="", error="ValueError: boom"
    )


def _measured() -> BrowseState:
    """Finish a run over four metrics: the fixture most tests start from."""
    return start(
        (
            _outcome(NOQA, 0),
            _outcome(PYLINT, 4, paths=("src/mills/runner.py", "src/mills/diff.py")),
            _outcome(LOC, 900, guide=2000),
            _outcome(LEGACY, 7, paths=("src/views.py",)),
        )
    )


def _labels(state: BrowseState) -> list[str]:
    return [row.cells[0] for row in rows(state)]


def _metric_names(state: BrowseState) -> list[str]:
    return [row.cells[0] for row in rows(state) if row.kind is RowKind.METRIC]


def _unfolded(state: BrowseState, key: str) -> BrowseState:
    """Unfold one row the way the gate does: off the fold state it drew."""
    row = next(row for row in rows(state) if row.key == key)
    assert row.folded is not None
    return set_fold(state, key, folded=not row.folded)


def test_a_fresh_session_opens_folded_over_every_metric_it_was_given() -> None:
    state = _measured()

    assert _metric_names(state) == [
        "noqa-comment",
        "pylint-comment",
        "loc",
        "legacy-arch",
    ]
    # an outline of what was measured, not every hit it located
    assert not [row for row in rows(state) if row.kind is RowKind.OCCURRENCE]


def test_rows_nest_metrics_under_their_group_in_config_order() -> None:
    state = _measured()

    assert _labels(state) == [
        "linting",
        "noqa-comment",
        "pylint-comment",
        "size",
        "loc",
        UNGROUPED,
        "legacy-arch",
    ]
    assert [row.depth for row in rows(state)] == [0, 1, 1, 0, 1, 0, 1]


def test_a_metric_row_shows_the_rank_the_mill_gave_it_rather_than_its_own() -> None:
    """The value column reads the emoji off the outcome, undisputed."""
    outcome = _outcome(NOQA, 3)
    state = start((outcome, _outcome(PYLINT, 0)))

    header, noqa, *_ = rows(state)
    assert noqa.cells[2] == f"{outcome.emoji} 3"
    assert header.cells[2] == "🚧 3"  # the group's own rank, over its own sum


def test_an_errored_metric_says_so_and_raises_its_groups_error_flag() -> None:
    state = start((_failed(NOQA), _outcome(PYLINT, 1)))

    header, noqa, *_ = rows(state)
    assert noqa.cells[2] == "ERROR"
    assert header.cells[0] == "linting"
    assert not fold_quiet_groups(state).folded & {group_key("linting")}


def test_occurrences_are_child_rows_of_an_unfolded_metric() -> None:
    state = _measured()

    assert "src/mills/runner.py:1" not in _labels(state)

    state = _unfolded(state, metric_key("pylint-comment"))
    hits = [row for row in rows(state) if row.kind is RowKind.OCCURRENCE]
    assert [row.cells for row in hits] == [
        ("src/mills/runner.py:1", "", ""),
        ("src/mills/diff.py:1", "", ""),
    ]
    assert hits[0].occurrence == Occurrence(path="src/mills/runner.py", line=1)


def test_a_metric_with_nothing_under_it_is_not_foldable() -> None:
    # no hits, no description, and no range it can name: nothing to reveal
    spec = MetricSpec(name="bare", type="regex_count")
    outcome = MetricOutcome(
        spec=spec, range_names=(), emoji="🎉", result=MetricResult(value=0), guide=100
    )

    (bare,) = rows(start((outcome,)))

    assert bare.folded is None
    assert bare.parent is None


def test_an_unfolded_metric_says_what_it_measures_before_what_it_found() -> None:
    spec = MetricSpec(
        name="pylint-comment",
        type="regex_count",
        description="how many lint escapes we carry",
    )
    state = start((_outcome(spec, 1, paths=("src/a.py",)),))

    state = _unfolded(state, metric_key("pylint-comment"))

    assert [(row.kind, row.cells[0]) for row in rows(state)] == [
        (RowKind.METRIC, "pylint-comment"),
        (RowKind.DETAIL, "how many lint escapes we carry"),
        (RowKind.DETAIL, "ranges: src"),
        (RowKind.OCCURRENCE, "src/a.py:1"),
    ]
    # everything under a metric folds back into it
    assert {row.parent for row in rows(state) if row.kind is not RowKind.METRIC} == {
        metric_key("pylint-comment")
    }


def test_a_failed_metric_carries_its_error_where_the_reader_can_read_it() -> None:
    state = _unfolded(
        start((_failed(LEGACY, ranges=("src",)),)), metric_key("legacy-arch")
    )

    details = [row.cells[0] for row in rows(state) if row.kind is RowKind.DETAIL]

    assert details == ["ranges: src", "ValueError: boom"]


def test_folding_a_group_hides_its_metrics_but_not_the_others() -> None:
    state = set_fold(_measured(), group_key("linting"), folded=True)

    assert _labels(state) == ["linting", "size", "loc", UNGROUPED, "legacy-arch"]


def test_fold_all_folds_every_group_then_unfolds_them_together() -> None:
    state = toggle_fold_all(_measured())

    assert _labels(state) == ["linting", "size", UNGROUPED]

    state = toggle_fold_all(state)
    assert _metric_names(state) == [
        "noqa-comment",
        "pylint-comment",
        "loc",
        "legacy-arch",
    ]


def test_fold_all_collapses_the_metrics_when_the_run_has_no_groups() -> None:
    spec = MetricSpec(name="todo", type="regex_count")
    state = _unfolded(
        start((_outcome(spec, 2, paths=("src/a.py",)),)), metric_key("todo")
    )
    assert _labels(state) == ["todo", "ranges: src", "src/a.py:1"]

    state = toggle_fold_all(state)

    assert _labels(state) == ["todo"]


def test_fold_all_leaves_a_listing_with_nothing_foldable_alone() -> None:
    # ungrouped, and with nothing to say about itself: no group header to
    # fold and no rows underneath the one metric
    bare = MetricOutcome(
        spec=MetricSpec(name="bare", type="regex_count"),
        range_names=(),
        emoji="🎉",
        result=MetricResult(value=0),
    )

    state = start((bare,))

    assert toggle_fold_all(state) is state


def test_a_finished_report_folds_away_the_groups_with_nothing_to_report() -> None:
    state = start(
        (
            _outcome(NOQA, 0),
            _outcome(PYLINT, 0),
            _outcome(LOC, 900, guide=2000),
            _outcome(LEGACY, 7),
        )
    )

    state = fold_quiet_groups(state)

    # linting measured nothing at all, so it folds; the others did, so they stay
    assert _labels(state) == ["linting", "size", "loc", UNGROUPED, "legacy-arch"]


def test_a_group_holding_an_error_is_never_folded_away() -> None:
    state = start((_failed(NOQA), _outcome(PYLINT, 0)))

    state = fold_quiet_groups(state)

    assert group_key("linting") not in state.folded


def test_a_diff_group_the_branch_did_not_move_folds_away() -> None:
    quiet = MetricSpec(name="still", type="file_count", group="quiet")
    outcome = DiffOutcome(
        spec=quiet,
        range_names=("src",),
        emoji="🦠",
        result=DiffResult(net=0, added=0, removed=0),
        total=MetricResult(value=12),
        guide=100,
    )

    state = fold_quiet_groups(start((outcome,)))

    assert _labels(state) == ["quiet"]


def test_grouped_reads_every_outcome_not_whatever_the_view_left_visible() -> None:
    state = _measured()

    assert grouped(state)
    # a search that spared only the ungrouped metric, and a sort that
    # flattened the outline, both leave it a grouped run
    assert grouped(set_query(state, "legacy"))
    assert grouped(push_sort(state, SortKey.NAME))
    assert not grouped(start((_outcome(LEGACY, 1),)))


def test_push_sort_stacks_and_moves_a_repeated_key_to_the_front() -> None:
    state = push_sort(
        push_sort(push_sort(_measured(), SortKey.NAME), SortKey.TYPE), SortKey.NAME
    )

    assert state.sort == (Sort(SortKey.NAME), Sort(SortKey.TYPE))


def test_pushing_a_key_the_other_way_up_turns_it_over_rather_than_stacking() -> None:
    state = push_sort(push_sort(_measured(), SortKey.VALUE), SortKey.NAME)

    state = push_sort(state, SortKey.VALUE, descending=True)

    assert state.sort == (Sort(SortKey.VALUE, descending=True), Sort(SortKey.NAME))


def test_a_descending_sort_is_the_ascending_one_turned_over() -> None:
    state = start((_outcome(NOQA, 5), _outcome(PYLINT, 40), _outcome(LOC, 900)))

    assert _metric_names(push_sort(state, SortKey.VALUE)) == [
        "noqa-comment",
        "pylint-comment",
        "loc",
    ]
    assert _metric_names(push_sort(state, SortKey.VALUE, descending=True)) == [
        "loc",
        "pylint-comment",
        "noqa-comment",
    ]


def test_what_a_key_cannot_place_stays_last_whichever_way_the_sort_runs() -> None:
    state = start(
        (_outcome(NOQA, 5), _failed(PYLINT), _outcome(LOC, 900), _failed(LEGACY))
    )

    for descending in (False, True):
        names = _metric_names(push_sort(state, SortKey.VALUE, descending=descending))

        assert names[-2:] == ["legacy-arch", "pylint-comment"]


def test_the_ungrouped_section_stays_last_whichever_way_groups_run() -> None:
    ascending = _labels(push_sort(_measured(), SortKey.GROUP))
    descending = _labels(push_sort(_measured(), SortKey.GROUP, descending=True))

    assert ascending[0] == "linting"
    assert descending[0] == "size"
    assert ascending[-2] == descending[-2] == UNGROUPED


def test_sorting_by_name_then_by_type_gives_type_major_order() -> None:
    state = push_sort(push_sort(_measured(), SortKey.NAME), SortKey.TYPE)

    assert _metric_names(state) == [
        "loc",  # file_lines
        "noqa-comment",  # regex_count, then by name
        "pylint-comment",
        "legacy-arch",  # symbol_uses
    ]


def test_a_non_group_primary_key_flattens_the_view_and_disables_folding() -> None:
    state = push_sort(_measured(), SortKey.NAME)

    assert not outlined(state)
    assert [row.kind for row in rows(state)] == [RowKind.METRIC] * 4
    assert _metric_names(state) == [
        "legacy-arch",
        "loc",
        "noqa-comment",
        "pylint-comment",
    ]
    assert all(row.folded is None for row in rows(state))


def test_a_group_primary_key_keeps_the_outline_and_orders_groups_by_name() -> None:
    state = push_sort(push_sort(_measured(), SortKey.NAME), SortKey.GROUP)

    assert outlined(state)
    assert _labels(state) == [
        "linting",
        "noqa-comment",
        "pylint-comment",
        "size",
        "loc",
        UNGROUPED,
        "legacy-arch",
    ]


def test_sorting_by_value_puts_the_biggest_first_and_the_errored_last() -> None:
    state = start(
        (_outcome(NOQA, 5), _failed(PYLINT), _outcome(LOC, 900), _failed(LEGACY))
    )

    state = push_sort(state, SortKey.VALUE, descending=True)

    assert _metric_names(state) == [
        "loc",
        "noqa-comment",
        "legacy-arch",  # measured nothing, so nothing to rank
        "pylint-comment",
    ]


def test_sorting_a_diff_run_by_value_ranks_the_standing_total_not_the_net() -> None:
    state = start(
        (
            DiffOutcome(
                spec=NOQA,
                range_names=("src",),
                emoji="🦠",
                result=DiffResult(net=9),
                total=MetricResult(value=2),
                guide=100,
            ),
            _outcome(LOC, 30),
        )
    )

    # the branch moved noqa-comment more; the debt it sits on is still smaller
    assert _metric_names(push_sort(state, SortKey.VALUE, descending=True)) == [
        "loc",
        "noqa-comment",
    ]


def test_sorting_by_score_puts_a_metric_with_no_score_last() -> None:
    state = start((_outcome(NOQA, 5), _failed(PYLINT)))

    assert _metric_names(push_sort(state, SortKey.SCORE, descending=True)) == [
        "noqa-comment",
        "pylint-comment",  # measured nothing, so it has no score to rank
    ]


def test_sorting_by_score_ranks_against_each_metrics_own_guide() -> None:
    state = start((_outcome(NOQA, 5, guide=5), _outcome(LOC, 900, guide=100_000)))

    by_value = push_sort(state, SortKey.VALUE, descending=True)
    by_score = push_sort(state, SortKey.SCORE, descending=True)

    assert _metric_names(by_value) == ["loc", "noqa-comment"]
    assert _metric_names(by_score) == ["noqa-comment", "loc"]


def test_folds_survive_a_sort_that_hid_them_and_come_back_on_reset() -> None:
    state = set_fold(_measured(), group_key("linting"), folded=True)

    state = push_sort(state, SortKey.NAME)
    assert _metric_names(state) == [
        "legacy-arch",
        "loc",
        "noqa-comment",
        "pylint-comment",
    ]

    state = clear_sort(state)
    assert _labels(state) == ["linting", "size", "loc", UNGROUPED, "legacy-arch"]


def test_a_diff_row_shows_the_branch_impact_beside_the_standing_total() -> None:
    outcome = DiffOutcome(
        spec=NOQA,
        range_names=("src",),
        emoji="🚨",
        result=DiffResult(net=2, added=3, removed=1),
        total=MetricResult(value=24),
        guide=100,
    )

    header, noqa, *_ = rows(start((outcome,)))
    assert noqa.cells[2] == "+3 / -1 (net +2 of 🚨 24)"
    assert header.cells[2] == "net +2 of 🚨 24"


def test_a_diff_with_no_standing_total_says_the_total_is_unknown() -> None:
    """Only the total is unknown; what the branch moved is still known."""
    outcome = DiffOutcome(
        spec=NOQA,
        range_names=("src",),
        emoji="",
        result=DiffResult(net=2, added=3, removed=1),
        guide=100,
    )

    header, noqa, *_ = rows(start((outcome,)))
    assert noqa.cells[2] == "+3 / -1 (net +2 of ?)"
    # and a group holding it cannot claim a standing debt of its own
    assert header.cells[2] == "net +2 of ?"


def test_a_diff_reporting_only_a_net_shows_the_standing_total_alone() -> None:
    outcome = DiffOutcome(
        spec=NOQA,
        range_names=("src",),
        emoji="🚨",
        result=DiffResult(net=-3),
        total=MetricResult(value=24),
        guide=100,
    )

    _, noqa, *_ = rows(start((outcome,)))
    assert noqa.cells[2] == "net -3 of 🚨 24"


def test_search_matches_a_metric_by_its_own_name() -> None:
    state = set_query(_measured(), "pylint")

    assert _labels(state) == ["linting", "pylint-comment"]


def test_search_is_case_sensitive() -> None:
    assert _labels(set_query(_measured(), "Pylint")) == []


def test_a_group_name_match_shows_every_metric_in_the_group() -> None:
    state = set_query(_measured(), "lint")

    assert _labels(state) == ["linting", "noqa-comment", "pylint-comment"]


def test_a_description_match_opens_the_metric_on_the_words_that_matched() -> None:
    spec = MetricSpec(
        name="loc",
        type="file_lines",
        description="how much code there is to maintain",
        group="size",
    )
    state = start((_outcome(spec, 900, paths=("src/mills/browse.py",)),))

    state = set_query(state, "maintain")

    # opened on the words that matched: a metric found through its
    # description must show that description, or the row gives no reason
    assert _labels(state) == [
        "size",
        "loc",
        "how much code there is to maintain",
        "ranges: src",
        "src/mills/browse.py:1",
    ]


def test_a_range_name_match_finds_the_range_the_run_resolved() -> None:
    outcome = MetricOutcome(
        spec=LEGACY,
        range_names=("python-source",),
        emoji="",
        result=MetricResult(value=7),
        guide=100,
    )

    assert _labels(set_query(start((outcome,)), "python-source")) == [
        "legacy-arch",
        "ranges: python-source",
    ]
    # the name the run resolved is the only one there is: a metric that
    # left the default range implied is searchable by what it ended up on
    assert _labels(set_query(start((outcome,)), "docs")) == []


def test_a_name_match_leaves_the_metric_folded_as_the_reader_left_it() -> None:
    state = set_fold(_measured(), metric_key("pylint-comment"), folded=True)

    state = set_query(state, "pylint")

    assert _labels(state) == ["linting", "pylint-comment"]


def test_a_file_match_reveals_the_metric_showing_only_the_matching_hits() -> None:
    state = set_query(_measured(), "runner.py")

    assert _labels(state) == [
        "linting",
        "pylint-comment",
        "ranges: src",
        "src/mills/runner.py:1",
    ]


def test_a_search_finds_a_file_inside_a_folded_metric_inside_a_folded_group() -> None:
    state = set_fold(_measured(), metric_key("pylint-comment"), folded=True)
    state = set_fold(state, group_key("linting"), folded=True)
    assert _labels(state) == ["linting", "size", "loc", UNGROUPED, "legacy-arch"]

    state = set_query(state, "views.py")

    assert _labels(state) == [UNGROUPED, "legacy-arch", "ranges: src", "src/views.py:1"]


def test_an_explicit_fold_during_a_search_beats_the_reveal() -> None:
    state = set_query(_measured(), "runner.py")
    revealed = next(
        row for row in rows(state) if row.key == metric_key("pylint-comment")
    )
    assert revealed.folded is False  # the query opened it

    state = set_fold(state, revealed.key, folded=True)

    assert _labels(state) == ["linting", "pylint-comment"]


def test_a_row_folded_during_a_search_can_be_unfolded_again_inside_it() -> None:
    """The second gesture replaces the first rather than stacking on it."""
    state = set_query(_measured(), "runner.py")
    state = set_fold(state, group_key("linting"), folded=True)
    assert _labels(state) == ["linting"]

    state = set_fold(state, group_key("linting"), folded=False)

    # and the search's own reveal is back with it, hit and all
    assert _labels(state) == [
        "linting",
        "pylint-comment",
        "ranges: src",
        "src/mills/runner.py:1",
    ]


def test_leaving_the_search_restores_the_fold_state_untouched() -> None:
    state = set_fold(_measured(), metric_key("pylint-comment"), folded=True)
    before = _labels(state)

    state = set_query(state, "runner.py")
    state = set_fold(state, group_key("linting"), folded=True)
    state = set_query(state, "")

    assert state.search is None
    assert _labels(state) == before


def test_a_search_that_matches_nothing_empties_the_view() -> None:
    assert not rows(set_query(_measured(), "nothing-matches-this"))
