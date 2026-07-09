from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING

from tingle.mills.metrics.symbol_uses import symbol_uses_diff
from tingle.pacts.diff import DiffMetricContext, DiffResult, FileDiff, FileStatus

if TYPE_CHECKING:
    from collections.abc import Mapping

SYMBOL = "myapp.legacy.OldClient"


def _run(
    file: FileDiff,
    current: Mapping[str, str | None],
    base: Mapping[str, str | None],
) -> DiffResult:
    return symbol_uses_diff(
        DiffMetricContext(
            files=(file,),
            read=lambda path: current.get(str(path)),
            read_base=lambda path: base.get(str(path)),
            params={"symbol": SYMBOL},
        )
    )


def test_counts_uses_on_added_lines() -> None:
    code = (
        "from myapp.legacy import OldClient\n"
        "\n"
        "first = OldClient()\n"
        "new = OldClient()\n"
    )
    file = FileDiff(
        path=PurePath("a.py"),
        status=FileStatus.MODIFIED,
        added_lines=frozenset({4}),
    )

    result = _run(file, {"a.py": code}, {})

    assert result.added == 1
    assert result.removed == 0
    assert result.net == 1
    assert [str(o) for o in result.added_occurrences] == ["a.py:4"]


def test_counts_uses_on_removed_lines_from_base() -> None:
    base_code = "from myapp.legacy import OldClient\n\ngone = OldClient()\n"
    file = FileDiff(
        path=PurePath("a.py"),
        status=FileStatus.MODIFIED,
        removed_lines=frozenset({3}),
    )

    result = _run(file, {"a.py": "clean = 1\n"}, {"a.py": base_code})

    assert result.added == 0
    assert result.removed == 1
    assert result.net == -1


def test_import_line_counts_as_use() -> None:
    code = "from myapp.legacy import OldClient\n"
    file = FileDiff(
        path=PurePath("a.py"),
        status=FileStatus.ADDED,
        added_lines=frozenset({1}),
    )

    result = _run(file, {"a.py": code}, {})

    assert result.added == 1


def test_untouched_uses_do_not_count() -> None:
    code = "from myapp.legacy import OldClient\n\nold = OldClient()\nx = 1\n"
    file = FileDiff(
        path=PurePath("a.py"),
        status=FileStatus.MODIFIED,
        added_lines=frozenset({4}),
    )

    result = _run(file, {"a.py": code}, {})

    assert result.added == 0
    assert result.net == 0


def test_base_syntax_error_warns_and_skips_side() -> None:
    file = FileDiff(
        path=PurePath("a.py"),
        status=FileStatus.MODIFIED,
        added_lines=frozenset({1}),
        removed_lines=frozenset({1}),
    )

    result = _run(
        file,
        {"a.py": "from myapp.legacy import OldClient\n"},
        {"a.py": "def broken(:\n"},
    )

    assert result.added == 1
    assert result.removed == 0
    assert any("base side skipped (syntax error" in w for w in result.warnings)


def test_unreadable_current_side_warns() -> None:
    file = FileDiff(
        path=PurePath("a.py"),
        status=FileStatus.MODIFIED,
        added_lines=frozenset({1}),
    )

    result = _run(file, {}, {})

    assert result.added == 0
    assert "a.py: current side unreadable" in result.warnings


def test_non_python_files_ignored() -> None:
    file = FileDiff(
        path=PurePath("notes.md"),
        status=FileStatus.ADDED,
        added_lines=frozenset({1}),
    )

    result = _run(file, {"notes.md": "myapp.legacy.OldClient\n"}, {})

    assert result.net == 0
    assert result.warnings == ()


def test_details_show_per_file_net() -> None:
    code = "from myapp.legacy import OldClient\n"
    file = FileDiff(
        path=PurePath("a.py"),
        status=FileStatus.ADDED,
        added_lines=frozenset({1}),
    )

    result = _run(file, {"a.py": code}, {})

    assert dict(result.details) == {"a.py": 1}
