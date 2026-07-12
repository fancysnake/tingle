from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING, Any

from tingle.mills.metrics.regex_count import regex_count, regex_count_diff
from tingle.mills.metrics.regex_count import validate_params as validate_regex
from tingle.mills.metrics.symbol_uses import symbol_uses, symbol_uses_diff
from tingle.mills.metrics.symbol_uses import validate_params as validate_symbol
from tingle.pacts.diff import DiffMetricContext, FileDiff, FileStatus
from tingle.pacts.metrics import MetricContext

if TYPE_CHECKING:
    from collections.abc import Mapping

# The case this feature exists for: ANY is real debt in an assertion, but
# harmless as a placeholder for a form that cannot be compared.
ASSERTIONS = """\
from unittest.mock import ANY


def test_create() -> None:
    assert response == {"form": ANY, "id": 3}


def test_update() -> None:
    assert result == ANY
"""


def _context(contents: Mapping[str, str], params: Mapping[str, Any]) -> MetricContext:
    return MetricContext(
        files=tuple(PurePath(name) for name in contents),
        read=lambda path: contents.get(str(path)),
        exists=lambda path: str(path) in contents,
        params=params,
    )


def _diff_context(
    current: Mapping[str, str],
    *,
    base: Mapping[str, str],
    files: tuple[FileDiff, ...],
    params: Mapping[str, Any],
) -> DiffMetricContext:
    return DiffMetricContext(
        files=files,
        read=lambda path: current.get(str(path)),
        read_base=lambda path: base.get(str(path)),
        params=params,
    )


def test_symbol_uses_ignores_the_placeholder_line() -> None:
    ctx = _context(
        {"test_api.py": ASSERTIONS},
        {"symbol": "ANY", "ignore_lines": [r'"form":\s*ANY']},
    )

    result = symbol_uses(ctx)

    # the import and `result == ANY` remain; `"form": ANY` is excused
    assert result.value == 2
    assert [o.line for o in result.occurrences] == [1, 9]


def test_symbol_uses_without_ignore_lines_counts_everything() -> None:
    ctx = _context({"test_api.py": ASSERTIONS}, {"symbol": "ANY"})

    assert symbol_uses(ctx).value == 3


def test_ignore_lines_searches_anywhere_in_the_line() -> None:
    """Unanchored: indentation and trailing code must not defeat the pattern."""
    text = 'x = 1\n    call(a, "form": ANY, b)\n'
    ctx = _context({"a.py": text}, {"symbol": "ANY", "ignore_lines": [r'"form": ANY']})

    assert symbol_uses(ctx).value == 0


def test_regex_count_ignores_matching_lines() -> None:
    text = "import os  # noqa: F401\nx = 1  # noqa: E501\n"
    ctx = _context({"a.py": text}, {"pattern": r"#\s*noqa", "ignore_lines": [r"F401"]})

    result = regex_count(ctx)

    assert result.value == 1
    assert result.details == {"a.py": 1}


def test_ignored_occurrences_leave_no_trace_in_details() -> None:
    """A file whose every hit is ignored must not appear at all."""
    ctx = _context(
        {"a.py": 'assert x == {"form": ANY}\n'},
        {"symbol": "ANY", "ignore_lines": [r'"form":\s*ANY']},
    )

    result = symbol_uses(ctx)

    assert result.value == 0
    assert not result.details
    assert not result.occurrences


def test_diff_filters_both_sides() -> None:
    """A line ignored on the branch must be ignored in the base, or net lies."""
    base = {"a.py": "from unittest.mock import ANY\n\nassert x == ANY\n"}
    current = {"a.py": 'from unittest.mock import ANY\n\nassert x == {"form": ANY}\n'}
    files = (
        FileDiff(
            path=PurePath("a.py"),
            status=FileStatus.MODIFIED,
            added_lines=frozenset({3}),
            removed_lines=frozenset({3}),
        ),
    )
    ctx = _diff_context(
        current,
        base=base,
        files=files,
        params={"symbol": "ANY", "ignore_lines": [r'"form":\s*ANY']},
    )

    result = symbol_uses_diff(ctx)

    # the added line is excused; the removed bare `ANY` still counts as paid off
    assert result.added == 0
    assert result.removed == 1
    assert result.net == -1


def test_diff_without_ignores_counts_both_sides() -> None:
    base = {"a.py": "x = ANY\n"}
    current = {"a.py": 'x = {"form": ANY}\n'}
    files = (
        FileDiff(
            path=PurePath("a.py"),
            status=FileStatus.MODIFIED,
            added_lines=frozenset({1}),
            removed_lines=frozenset({1}),
        ),
    )
    ctx = _diff_context(current, base=base, files=files, params={"symbol": "ANY"})

    result = symbol_uses_diff(ctx)

    assert result.added == 1
    assert result.removed == 1
    assert result.net == 0


def test_regex_count_diff_filters_the_added_side() -> None:
    current = {"a.py": "x = 1  # noqa: F401\n"}
    files = (
        FileDiff(
            path=PurePath("a.py"), status=FileStatus.ADDED, added_lines=frozenset({1})
        ),
    )
    ctx = _diff_context(
        current,
        base={},
        files=files,
        params={"pattern": r"#\s*noqa", "ignore_lines": [r"F401"]},
    )

    assert regex_count_diff(ctx).added == 0


def test_validate_rejects_a_non_list() -> None:
    errors = validate_symbol({"symbol": "ANY", "ignore_lines": "F401"})

    assert "ignore_lines must be a list of strings" in errors


def test_validate_rejects_a_non_string_entry() -> None:
    errors = validate_regex({"pattern": "x", "ignore_lines": [3]})

    assert "ignore_lines must be a list of strings" in errors


def test_validate_rejects_an_uncompilable_pattern() -> None:
    errors = validate_regex({"pattern": "x", "ignore_lines": ["("]})

    assert any(error.startswith("invalid ignore_lines pattern '('") for error in errors)


def test_validate_accepts_no_ignore_lines() -> None:
    assert not validate_symbol({"symbol": "ANY"})
