from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING, Any

from tingle.mills.metrics.symbol_uses import symbol_spread
from tingle.pacts.metrics import MetricContext

if TYPE_CHECKING:
    from collections.abc import Mapping


def _context(
    contents: Mapping[str, str | None], params: Mapping[str, Any]
) -> MetricContext:
    return MetricContext(
        files=tuple(PurePath(name) for name in contents),
        read=lambda path: contents.get(str(path)),
        exists=lambda path: str(path) in contents,
        params=params,
    )


def test_counts_a_file_once_however_many_references() -> None:
    source = "x = OldClient()\ny = OldClient()\nz = OldClient()\n"

    result = symbol_spread(_context({"a.py": source}, {"symbol": "OldClient"}))

    assert result.value == 1
    assert [str(o) for o in result.occurrences] == ["a.py:1"]
    assert dict(result.details) == {"a.py": 3}


def test_counts_each_referencing_file() -> None:
    contents = {
        "a.py": "x = OldClient()\n",
        "b.py": "x = 1\n",
        "c.py": "y = OldClient()\nz = OldClient()\n",
    }

    result = symbol_spread(_context(contents, {"symbol": "OldClient"}))

    assert result.value == 2
    assert [str(o) for o in result.occurrences] == ["a.py:1", "c.py:1"]


def test_occurrence_points_at_the_first_reference() -> None:
    source = "import os\n\n\nx = OldClient()\ny = OldClient()\n"

    result = symbol_spread(_context({"a.py": source}, {"symbol": "OldClient"}))

    assert [str(o) for o in result.occurrences] == ["a.py:4"]


def test_dotted_symbol_counts_the_importing_file_once() -> None:
    source = "from myapp.legacy import OldClient\n\nx = OldClient()\ny = OldClient()\n"

    result = symbol_spread(
        _context({"a.py": source}, {"symbol": "myapp.legacy.OldClient"})
    )

    assert result.value == 1
    # the import itself is a use, so the first hit is line 1
    assert [str(o) for o in result.occurrences] == ["a.py:1"]


def test_non_python_files_are_skipped() -> None:
    contents = {"a.py": "x = OldClient()\n", "notes.md": "OldClient everywhere\n"}

    result = symbol_spread(_context(contents, {"symbol": "OldClient"}))

    assert result.value == 1
    assert not result.warnings


def test_file_whose_every_reference_is_excused_does_not_count() -> None:
    contents = {"a.py": 'assert x == {"form": ANY}\n', "b.py": "assert y == ANY\n"}

    result = symbol_spread(
        _context(contents, {"symbol": "ANY", "ignore_lines": [r'"form":\s*ANY']})
    )

    assert result.value == 1
    assert [str(o) for o in result.occurrences] == ["b.py:1"]


def test_syntax_error_warns_and_does_not_count() -> None:
    contents = {"a.py": "def (:\n", "b.py": "x = OldClient()\n"}

    result = symbol_spread(_context(contents, {"symbol": "OldClient"}))

    assert result.value == 1
    assert len(result.warnings) == 1
    assert result.warnings[0].startswith("a.py: skipped (syntax error:")


def test_star_import_falls_back_with_a_warning() -> None:
    source = "from myapp.legacy import *\n\nx = OldClient()\n"

    result = symbol_spread(
        _context({"a.py": source}, {"symbol": "myapp.legacy.OldClient"})
    )

    assert result.value == 1
    assert result.warnings == ("a.py: star import: falling back to bare-name counting",)


def test_no_reference_is_zero() -> None:
    result = symbol_spread(_context({"a.py": "x = 1\n"}, {"symbol": "OldClient"}))

    assert result.value == 0
    assert not result.occurrences
