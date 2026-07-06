from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING, Any

from tingle.mills.metrics.regex_count import regex_count_diff
from tingle.pacts.diff import DiffMetricContext, FileDiff, FileStatus

if TYPE_CHECKING:
    from collections.abc import Mapping


def _context(
    files: tuple[FileDiff, ...],
    current: Mapping[str, str | None],
    base: Mapping[str, str | None],
    params: Mapping[str, Any],
) -> DiffMetricContext:
    return DiffMetricContext(
        files=files,
        read=lambda path: current.get(str(path)),
        read_base=lambda path: base.get(str(path)),
        params=params,
    )


def test_counts_only_on_added_lines() -> None:
    file = FileDiff(
        path=PurePath("a.py"),
        status=FileStatus.MODIFIED,
        added_lines=frozenset({2}),
    )
    current = {"a.py": "x = 1  # noqa\ny = 2  # noqa\nz = 3  # noqa\n"}

    result = regex_count_diff(
        _context((file,), current, {}, {"pattern": r"#\s*noqa"})
    )

    assert result.added == 1
    assert result.removed == 0
    assert result.net == 1
    assert [str(o) for o in result.added_occurrences] == ["a.py:2"]
    assert result.removed_occurrences == ()


def test_removed_side_uses_base_content() -> None:
    file = FileDiff(
        path=PurePath("a.py"),
        status=FileStatus.MODIFIED,
        removed_lines=frozenset({1, 2}),
    )
    base = {"a.py": "x = 1  # noqa\ny = 2  # noqa\nz = 3  # noqa\n"}

    result = regex_count_diff(
        _context((file,), {"a.py": "clean\n"}, base, {"pattern": r"#\s*noqa"})
    )

    assert result.added == 0
    assert result.removed == 2
    assert result.net == -2
    assert [str(o) for o in result.removed_occurrences] == ["a.py:1", "a.py:2"]


def test_modified_line_with_surviving_match_is_net_zero() -> None:
    file = FileDiff(
        path=PurePath("a.py"),
        status=FileStatus.MODIFIED,
        added_lines=frozenset({1}),
        removed_lines=frozenset({1}),
    )
    result = regex_count_diff(
        _context(
            (file,),
            {"a.py": "y = 2  # noqa\n"},
            {"a.py": "x = 1  # noqa\n"},
            {"pattern": r"#\s*noqa"},
        )
    )

    assert result.added == 1
    assert result.removed == 1
    assert result.net == 0
    assert dict(result.details) == {}


def test_multiple_matches_per_line() -> None:
    file = FileDiff(
        path=PurePath("a.py"),
        status=FileStatus.ADDED,
        added_lines=frozenset({1}),
    )
    result = regex_count_diff(
        _context((file,), {"a.py": "TODO and TODO again\n"}, {}, {"pattern": "TODO"})
    )

    assert result.added == 2


def test_newline_patterns_never_match_in_diff_mode() -> None:
    file = FileDiff(
        path=PurePath("a.py"),
        status=FileStatus.ADDED,
        added_lines=frozenset({1, 2}),
    )
    result = regex_count_diff(
        _context((file,), {"a.py": "one\ntwo\n"}, {}, {"pattern": r"one\ntwo"})
    )

    assert result.added == 0


def test_unreadable_sides_warn() -> None:
    file = FileDiff(
        path=PurePath("blob.bin"),
        status=FileStatus.MODIFIED,
        added_lines=frozenset({1}),
        removed_lines=frozenset({1}),
    )
    result = regex_count_diff(_context((file,), {}, {}, {"pattern": "x"}))

    assert result.net == 0
    assert "blob.bin: current side unreadable" in result.warnings
    assert "blob.bin: base side unreadable" in result.warnings


def test_empty_line_sets_do_not_warn() -> None:
    file = FileDiff(path=PurePath("blob.bin"), status=FileStatus.MODIFIED)

    result = regex_count_diff(_context((file,), {}, {}, {"pattern": "x"}))

    assert result.warnings == ()
