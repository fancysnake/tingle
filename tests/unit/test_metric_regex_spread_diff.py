from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING, Any

from tingle.mills.metrics.regex_count import regex_spread_diff
from tingle.pacts.diff import DiffMetricContext, FileDiff, FileStatus

if TYPE_CHECKING:
    from collections.abc import Mapping

NOQA = {"pattern": r"#\s*noqa"}


def _context(
    files: tuple[FileDiff, ...],
    current: Mapping[str, str | None],
    *,
    base: Mapping[str, str | None],
    params: Mapping[str, Any] | None = None,
) -> DiffMetricContext:
    return DiffMetricContext(
        files=files,
        read=lambda path: current.get(str(path)),
        read_base=lambda path: base.get(str(path)),
        params=params if params is not None else NOQA,
    )


def _modified(name: str, **lines: frozenset[int]) -> FileDiff:
    return FileDiff(path=PurePath(name), status=FileStatus.MODIFIED, **lines)


def test_first_match_in_a_file_is_spread_taken_on() -> None:
    result = regex_spread_diff(
        _context(
            (_modified("a.py", added_lines=frozenset({1})),),
            {"a.py": "x = 1  # noqa\n"},
            base={"a.py": "x = 1\n"},
        )
    )

    assert result.added == 1
    assert result.net == 1
    assert [str(o) for o in result.added_occurrences] == ["a.py"]


def test_last_match_removed_is_spread_contained() -> None:
    result = regex_spread_diff(
        _context(
            (_modified("a.py", removed_lines=frozenset({1})),),
            {"a.py": "x = 1\n"},
            base={"a.py": "x = 1  # noqa\n"},
        )
    )

    assert result.removed == 1
    assert result.net == -1
    assert [str(o) for o in result.removed_occurrences] == ["a.py"]


def test_rewriting_a_file_that_already_matched_nets_zero() -> None:
    # the motivating case: fixing a bug in legacy code churns matching
    # lines without spreading anything
    current = {"a.py": "a = 1  # noqa\nb = 2  # noqa\nc = 3  # noqa\n"}
    base = {"a.py": "a = 0  # noqa\n"}

    result = regex_spread_diff(
        _context(
            (
                _modified(
                    "a.py",
                    added_lines=frozenset({1, 2, 3}),
                    removed_lines=frozenset({1}),
                ),
            ),
            current,
            base=base,
        )
    )

    assert result.net == 0
    assert result.added == 0
    assert result.removed == 0
    assert not result.details


def test_adding_more_matches_to_a_file_that_had_none_counts_once() -> None:
    result = regex_spread_diff(
        _context(
            (_modified("a.py", added_lines=frozenset({1, 2, 3})),),
            {"a.py": "# noqa\n# noqa\n# noqa\n"},
            base={"a.py": "clean\n"},
        )
    )

    assert result.net == 1
    assert dict(result.details) == {"a.py": 1}


def test_created_file_with_a_match_counts() -> None:
    file = FileDiff(path=PurePath("new.py"), status=FileStatus.ADDED)

    result = regex_spread_diff(_context((file,), {"new.py": "# noqa\n"}, base={}))

    assert result.net == 1
    assert not result.warnings


def test_deleted_file_with_a_match_counts_against() -> None:
    file = FileDiff(path=PurePath("gone.py"), status=FileStatus.DELETED)

    result = regex_spread_diff(_context((file,), {}, base={"gone.py": "# noqa\n"}))

    assert result.net == -1
    assert not result.warnings


def test_spread_and_containment_offset_each_other() -> None:
    result = regex_spread_diff(
        _context(
            (_modified("a.py"), _modified("b.py")),
            {"a.py": "# noqa\n", "b.py": "clean\n"},
            base={"a.py": "clean\n", "b.py": "# noqa\n"},
        )
    )

    assert result.net == 0
    assert result.added == 1
    assert result.removed == 1


def test_multiline_pattern_matches_in_diff_mode() -> None:
    # unlike regex_count_diff, both sides are matched full-text, so a
    # pattern spanning a newline is not silently invisible here
    result = regex_spread_diff(
        _context(
            (_modified("a.py", added_lines=frozenset({2})),),
            {"a.py": "start\nend\n"},
            base={"a.py": "start\nother\n"},
            params={"pattern": "start\nend"},
        )
    )

    assert result.net == 1


def test_excused_lines_do_not_count_as_spread() -> None:
    result = regex_spread_diff(
        _context(
            (_modified("a.py", added_lines=frozenset({1})),),
            {"a.py": '{"form": ANY}\n'},
            base={"a.py": "clean\n"},
            params={"pattern": "ANY", "ignore_lines": [r'"form":\s*ANY']},
        )
    )

    assert result.net == 0


def test_unreadable_current_side_warns() -> None:
    result = regex_spread_diff(
        _context((_modified("a.py"),), {"a.py": None}, base={"a.py": "# noqa\n"})
    )

    assert result.warnings == ("a.py: current side unreadable",)
    assert result.net == -1
