from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING, Any

from tingle.mills.metrics.symbol_uses import symbol_spread_diff
from tingle.pacts.diff import DiffMetricContext, FileDiff, FileStatus

if TYPE_CHECKING:
    from collections.abc import Mapping

OLD_CLIENT = {"symbol": "OldClient"}


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
        params=params if params is not None else OLD_CLIENT,
    )


def _modified(name: str) -> FileDiff:
    return FileDiff(path=PurePath(name), status=FileStatus.MODIFIED)


def test_first_reference_in_a_file_is_spread_taken_on() -> None:
    result = symbol_spread_diff(
        _context(
            (_modified("a.py"),),
            {"a.py": "x = OldClient()\n"},
            base={"a.py": "x = 1\n"},
        )
    )

    assert result.added == 1
    assert result.net == 1
    assert [str(o) for o in result.added_occurrences] == ["a.py"]


def test_last_reference_removed_is_spread_contained() -> None:
    result = symbol_spread_diff(
        _context(
            (_modified("a.py"),),
            {"a.py": "x = 1\n"},
            base={"a.py": "x = OldClient()\n"},
        )
    )

    assert result.removed == 1
    assert result.net == -1
    assert [str(o) for o in result.removed_occurrences] == ["a.py"]


def test_reworking_a_file_that_already_referenced_it_nets_zero() -> None:
    # the motivating case: fixing a bug in legacy code multiplies the
    # references without spreading the class any further
    current = {"a.py": "a = OldClient()\nb = OldClient()\nc = OldClient()\n"}
    base = {"a.py": "a = OldClient()\n"}

    result = symbol_spread_diff(_context((_modified("a.py"),), current, base=base))

    assert result.net == 0
    assert result.added == 0
    assert result.removed == 0
    assert not result.details


def test_created_file_referencing_the_symbol_counts() -> None:
    file = FileDiff(path=PurePath("new.py"), status=FileStatus.ADDED)

    result = symbol_spread_diff(
        _context((file,), {"new.py": "x = OldClient()\n"}, base={})
    )

    assert result.net == 1
    assert not result.warnings


def test_deleted_file_referencing_the_symbol_counts_against() -> None:
    file = FileDiff(path=PurePath("gone.py"), status=FileStatus.DELETED)

    result = symbol_spread_diff(
        _context((file,), {}, base={"gone.py": "x = OldClient()\n"})
    )

    assert result.net == -1
    assert not result.warnings


def test_non_python_files_are_skipped() -> None:
    file = FileDiff(path=PurePath("notes.md"), status=FileStatus.ADDED)

    result = symbol_spread_diff(_context((file,), {"notes.md": "OldClient\n"}, base={}))

    assert result.net == 0
    assert not result.warnings


def test_dotted_symbol_follows_the_import() -> None:
    current = {"a.py": "from myapp.legacy import OldClient\n\nx = OldClient()\n"}

    result = symbol_spread_diff(
        _context(
            (_modified("a.py"),),
            current,
            base={"a.py": "x = 1\n"},
            params={"symbol": "myapp.legacy.OldClient"},
        )
    )

    assert result.net == 1


def test_excused_references_do_not_count_as_spread() -> None:
    result = symbol_spread_diff(
        _context(
            (_modified("a.py"),),
            {"a.py": 'assert x == {"form": ANY}\n'},
            base={"a.py": "x = 1\n"},
            params={"symbol": "ANY", "ignore_lines": [r'"form":\s*ANY']},
        )
    )

    assert result.net == 0


def test_syntax_error_on_one_side_names_that_side() -> None:
    result = symbol_spread_diff(
        _context(
            (_modified("a.py"),),
            {"a.py": "def (:\n"},
            base={"a.py": "x = OldClient()\n"},
        )
    )

    assert len(result.warnings) == 1
    assert result.warnings[0].startswith("a.py: current side: skipped (syntax error:")
    assert result.net == -1


def test_star_import_warning_names_its_side() -> None:
    current = {"a.py": "from myapp.legacy import *\n\nx = OldClient()\n"}

    result = symbol_spread_diff(
        _context(
            (_modified("a.py"),),
            current,
            base={"a.py": "x = 1\n"},
            params={"symbol": "myapp.legacy.OldClient"},
        )
    )

    assert result.net == 1
    assert result.warnings == (
        "a.py: current side: star import: falling back to bare-name counting",
    )


def test_unreadable_current_side_warns() -> None:
    result = symbol_spread_diff(
        _context(
            (_modified("a.py"),), {"a.py": None}, base={"a.py": "x = OldClient()\n"}
        )
    )

    assert result.warnings == ("a.py: current side unreadable",)
    assert result.net == -1
