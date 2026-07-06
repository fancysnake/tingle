from pathlib import PurePath
from typing import TYPE_CHECKING

from tingle.mills.metrics.counts import file_count, line_count
from tingle.pacts.metrics import MetricContext

if TYPE_CHECKING:
    from collections.abc import Mapping


def _context(contents: Mapping[str, str | None]) -> MetricContext:
    return MetricContext(
        files=tuple(PurePath(name) for name in contents),
        read=lambda path: contents.get(str(path)),
        exists=lambda path: str(path) in contents,
        params={},
    )


def test_file_count() -> None:
    result = file_count(_context({"a.py": "", "b.py": ""}))

    assert result.value == 2


def test_file_count_empty() -> None:
    result = file_count(_context({}))

    assert result.value == 0


def test_line_count_sums_lines_with_details() -> None:
    result = line_count(_context({"a.py": "one\ntwo\n", "b.py": "one\n"}))

    assert result.value == 3
    assert dict(result.details) == {"a.py": 2, "b.py": 1}
    assert result.warnings == ()


def test_line_count_skips_unreadable_with_warning() -> None:
    result = line_count(_context({"a.py": "one\n", "blob.bin": None}))

    assert result.value == 1
    assert result.warnings == ("blob.bin: skipped (binary, unreadable, or missing)",)
