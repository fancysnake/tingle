from __future__ import annotations

from support import metric_context

from tingle.mills.metrics.counts import file_count, line_count


def test_file_count() -> None:
    result = file_count(metric_context({"a.py": "", "b.py": ""}))

    assert result.value == 2
    assert [str(o) for o in result.occurrences] == ["a.py", "b.py"]


def test_file_count_empty() -> None:
    result = file_count(metric_context({}))

    assert result.value == 0


def test_line_count_sums_lines_with_details() -> None:
    result = line_count(metric_context({"a.py": "one\ntwo\n", "b.py": "one\n"}))

    assert result.value == 3
    assert dict(result.details) == {"a.py": 2, "b.py": 1}
    assert not result.warnings


def test_line_count_skips_unreadable_with_warning() -> None:
    result = line_count(metric_context({"a.py": "one\n", "blob.bin": None}))

    assert result.value == 1
    assert result.warnings == ("blob.bin: skipped (binary, unreadable, or missing)",)
