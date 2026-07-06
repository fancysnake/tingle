from pathlib import PurePath
from typing import TYPE_CHECKING, Any

from tingle.mills.metrics.regex_count import regex_count, validate_params
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


def test_counts_matches_across_files() -> None:
    result = regex_count(
        _context(
            {"a.py": "x = 1  # noqa\ny = 2  # noqa\n", "b.py": "z = 3  # noqa\n"},
            {"pattern": r"#\s*noqa"},
        )
    )

    assert result.value == 3
    assert dict(result.details) == {"a.py": 2, "b.py": 1}


def test_zero_matches_has_empty_details() -> None:
    result = regex_count(_context({"a.py": "clean\n"}, {"pattern": "TODO"}))

    assert result.value == 0
    assert dict(result.details) == {}


def test_flags_are_applied() -> None:
    result = regex_count(
        _context({"a.py": "TODO\ntodo\n"}, {"pattern": "todo", "flags": ["IGNORECASE"]})
    )

    assert result.value == 2


def test_unreadable_file_warns() -> None:
    result = regex_count(_context({"blob.bin": None}, {"pattern": "x"}))

    assert result.value == 0
    assert result.warnings == ("blob.bin: skipped (binary, unreadable, or missing)",)


def test_validate_params_accepts_valid() -> None:
    assert validate_params({"pattern": r"#\s*noqa", "flags": ["MULTILINE"]}) == []


def test_validate_params_rejects_bad_regex() -> None:
    errors = validate_params({"pattern": "("})

    assert len(errors) == 1
    assert "invalid pattern" in errors[0]


def test_validate_params_rejects_non_string_pattern() -> None:
    assert validate_params({"pattern": 5}) == ["pattern must be a string"]


def test_validate_params_rejects_unknown_flag() -> None:
    errors = validate_params({"pattern": "x", "flags": ["VERBOSE"]})

    assert errors == ["unknown flag 'VERBOSE' (allowed: DOTALL, IGNORECASE, MULTILINE)"]


def test_validate_params_rejects_non_list_flags() -> None:
    assert validate_params({"pattern": "x", "flags": "IGNORECASE"}) == [
        "flags must be a list of strings"
    ]
