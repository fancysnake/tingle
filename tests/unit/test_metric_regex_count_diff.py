from __future__ import annotations

from pathlib import PurePath

from support import diff_context, modified

from tingle.mills.metrics.regex_count import regex_count_diff
from tingle.pacts.diff import FileDiff, FileStatus

NOQA = {"pattern": r"#\s*noqa"}


def test_counts_only_on_added_lines() -> None:
    file = modified("a.py", added=frozenset({2}))
    current = {"a.py": "x = 1  # noqa\ny = 2  # noqa\nz = 3  # noqa\n"}

    result = regex_count_diff(diff_context(current, files=(file,), params=NOQA))

    assert result.added == 1
    assert result.removed == 0
    assert result.net == 1
    assert [str(o) for o in result.added_occurrences] == ["a.py:2"]
    assert not result.removed_occurrences


def test_removed_side_uses_base_content() -> None:
    file = modified("a.py", removed=frozenset({1, 2}))
    base = {"a.py": "x = 1  # noqa\ny = 2  # noqa\nz = 3  # noqa\n"}

    result = regex_count_diff(
        diff_context({"a.py": "clean\n"}, files=(file,), base=base, params=NOQA)
    )

    assert result.added == 0
    assert result.removed == 2
    assert result.net == -2
    assert [str(o) for o in result.removed_occurrences] == ["a.py:1", "a.py:2"]


def test_modified_line_with_surviving_match_is_net_zero() -> None:
    file = modified("a.py", added=frozenset({1}), removed=frozenset({1}))

    result = regex_count_diff(
        diff_context(
            {"a.py": "y = 2  # noqa\n"},
            files=(file,),
            base={"a.py": "x = 1  # noqa\n"},
            params=NOQA,
        )
    )

    assert result.added == 1
    assert result.removed == 1
    assert result.net == 0
    assert not result.details


def test_multiple_matches_per_line() -> None:
    file = FileDiff(
        path=PurePath("a.py"), status=FileStatus.ADDED, added_lines=frozenset({1})
    )

    result = regex_count_diff(
        diff_context(
            {"a.py": "TODO and TODO again\n"}, files=(file,), params={"pattern": "TODO"}
        )
    )

    assert result.added == 2


def test_newline_patterns_never_match_in_diff_mode() -> None:
    file = FileDiff(
        path=PurePath("a.py"), status=FileStatus.ADDED, added_lines=frozenset({1, 2})
    )

    result = regex_count_diff(
        diff_context(
            {"a.py": "one\ntwo\n"}, files=(file,), params={"pattern": r"one\ntwo"}
        )
    )

    assert result.added == 0


def test_unreadable_sides_warn() -> None:
    file = modified("blob.bin", added=frozenset({1}), removed=frozenset({1}))

    result = regex_count_diff(diff_context({}, files=(file,), params={"pattern": "x"}))

    assert result.net == 0
    assert "blob.bin: current side unreadable" in result.warnings
    assert "blob.bin: base side unreadable" in result.warnings


def test_empty_line_sets_do_not_warn() -> None:
    file = modified("blob.bin")

    result = regex_count_diff(diff_context({}, files=(file,), params={"pattern": "x"}))

    assert not result.warnings
