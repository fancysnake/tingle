from __future__ import annotations

from pathlib import PurePath

from tingle.mills.metrics.counts import file_count_diff, line_count_diff
from tingle.pacts.diff import DiffMetricContext, FileDiff, FileStatus


def _context(*files: FileDiff) -> DiffMetricContext:
    return DiffMetricContext(
        files=files, read=lambda _: None, read_base=lambda _: None, params={}
    )


def test_file_count_diff_counts_created_and_deleted() -> None:
    result = file_count_diff(
        _context(
            FileDiff(path=PurePath("new.py"), status=FileStatus.ADDED),
            FileDiff(path=PurePath("gone.py"), status=FileStatus.DELETED),
            FileDiff(path=PurePath("edited.py"), status=FileStatus.MODIFIED),
        )
    )

    assert result.added == 1
    assert result.removed == 1
    assert result.net == 0
    assert [str(o) for o in result.added_occurrences] == ["new.py"]
    assert [str(o) for o in result.removed_occurrences] == ["gone.py"]


def test_file_count_diff_empty() -> None:
    result = file_count_diff(_context())

    assert result.net == 0
    assert result.added == 0
    assert result.removed == 0


def test_line_count_diff_sums_touched_lines() -> None:
    result = line_count_diff(
        _context(
            FileDiff(
                path=PurePath("a.py"),
                status=FileStatus.MODIFIED,
                added_lines=frozenset({1, 2, 3}),
                removed_lines=frozenset({1}),
            ),
            FileDiff(
                path=PurePath("b.py"),
                status=FileStatus.DELETED,
                removed_lines=frozenset({1, 2}),
            ),
        )
    )

    assert result.added == 3
    assert result.removed == 3
    assert result.net == 0
    assert dict(result.details) == {"a.py": 2, "b.py": -2}
