from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tingle.mills.metrics.config_lists import (
    ini_list_length,
    toml_list_length,
    toml_table_array,
    validate_ini_params,
    validate_toml_params,
    validate_toml_table_array_params,
)
from tingle.pacts.metrics import MetricContext

if TYPE_CHECKING:
    from collections.abc import Mapping

MYPY_OVERRIDES = """
[[tool.mypy.overrides]]
module = "foo.*"
ignore_errors = true

[[tool.mypy.overrides]]
module = ["bar.baz", "bar.qux"]

[[tool.mypy.overrides]]
ignore_missing_imports = true
"""

PYPROJECT = """
[tool.ruff.lint]
ignore = ["E501", "D203", "ANN101"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "D103"]
"scripts/**" = ["T201"]

[tool.mypy]
disable_error_code = ["misc"]
"""

PYLINTRC = """
[MESSAGES CONTROL]
disable = too-many-arguments,
    missing-docstring,
    invalid-name

[FORMAT]
max-line-length = 100
"""


def _context(
    contents: Mapping[str, str | None], params: Mapping[str, Any]
) -> MetricContext:
    return MetricContext(
        files=(),
        read=lambda path: contents.get(str(path)),
        exists=lambda path: str(path) in contents,
        params=params,
    )


def test_toml_list_length_counts_entries() -> None:
    result = toml_list_length(
        _context({"pyproject.toml": PYPROJECT}, {"key": "tool.ruff.lint.ignore"})
    )

    assert result.value == 3
    assert result.warnings == ()
    assert [str(o) for o in result.occurrences] == [
        "pyproject.toml: E501",
        "pyproject.toml: D203",
        "pyproject.toml: ANN101",
    ]


def test_toml_file_defaults_to_pyproject() -> None:
    result = toml_list_length(
        _context({"pyproject.toml": PYPROJECT}, {"key": "tool.mypy.disable_error_code"})
    )

    assert result.value == 1


def test_toml_custom_file() -> None:
    result = toml_list_length(
        _context(
            {"ruff.toml": '[lint]\nignore = ["E501"]\n'},
            {"key": "lint.ignore", "file": "ruff.toml"},
        )
    )

    assert result.value == 1


def test_toml_table_of_lists_sums_lengths() -> None:
    result = toml_list_length(
        _context(
            {"pyproject.toml": PYPROJECT}, {"key": "tool.ruff.lint.per-file-ignores"}
        )
    )

    assert result.value == 3
    assert dict(result.details) == {"tests/**": 2, "scripts/**": 1}
    assert [o.note for o in result.occurrences] == [
        "tests/**: S101",
        "tests/**: D103",
        "scripts/**: T201",
    ]


def test_toml_non_list_value_warns() -> None:
    result = toml_list_length(
        _context({"pyproject.toml": PYPROJECT}, {"key": "tool.ruff"})
    )

    assert result.value == 0
    assert "is not a list or a table of lists" in result.warnings[0]


def test_toml_missing_key_warns() -> None:
    result = toml_list_length(
        _context({"pyproject.toml": PYPROJECT}, {"key": "tool.nope.ignore"})
    )

    assert result.value == 0
    assert 'key "tool.nope.ignore" not found' in result.warnings[0]


def test_toml_missing_file_warns() -> None:
    result = toml_list_length(_context({}, {"key": "tool.ruff.lint.ignore"}))

    assert result.value == 0
    assert "pyproject.toml: not found or unreadable" in result.warnings[0]


def test_toml_malformed_warns() -> None:
    result = toml_list_length(_context({"pyproject.toml": "[broken"}, {"key": "x"}))

    assert result.value == 0
    assert "invalid TOML" in result.warnings[0]


def test_validate_toml_params() -> None:
    assert validate_toml_params({"key": "tool.ruff.lint.ignore"}) == []
    assert validate_toml_params({"key": ""}) == ["key must be a non-empty string"]
    assert validate_toml_params({"key": "x", "file": 5}) == ["file must be a string"]


def test_table_array_counts_tables_and_labels_them() -> None:
    result = toml_table_array(
        _context(
            {"pyproject.toml": MYPY_OVERRIDES},
            {"key": "tool.mypy.overrides", "label": "module"},
        )
    )

    assert result.value == 3  # one per [[...]] block
    assert result.warnings == ()
    assert [str(o) for o in result.occurrences] == [
        "pyproject.toml: foo.*",
        "pyproject.toml: bar.baz, bar.qux",  # list label joined
        "pyproject.toml: #3",  # no label field -> index fallback
    ]


def test_table_array_without_label_uses_index_notes() -> None:
    result = toml_table_array(
        _context({"pyproject.toml": MYPY_OVERRIDES}, {"key": "tool.mypy.overrides"})
    )

    assert result.value == 3
    assert [o.note for o in result.occurrences] == ["#1", "#2", "#3"]


def test_table_array_default_file_is_pyproject() -> None:
    result = toml_table_array(
        _context({"pyproject.toml": MYPY_OVERRIDES}, {"key": "tool.mypy.overrides"})
    )

    assert result.value == 3


def test_table_array_empty_is_zero_without_warning() -> None:
    result = toml_table_array(
        _context({"pyproject.toml": "over = []\n"}, {"key": "over", "label": "module"})
    )

    # an empty array of tables vacuously satisfies "every element a table"
    assert result.value == 0
    assert result.occurrences == ()
    assert result.warnings == ()


def test_table_array_non_array_of_tables_warns() -> None:
    result = toml_table_array(
        _context({"pyproject.toml": "over = [1, 2]\n"}, {"key": "over"})
    )

    assert result.value == 0
    assert 'value at "over" is not an array of tables' in result.warnings[0]


def test_table_array_missing_key_warns() -> None:
    result = toml_table_array(
        _context({"pyproject.toml": MYPY_OVERRIDES}, {"key": "tool.nope"})
    )

    assert result.value == 0
    assert 'key "tool.nope" not found' in result.warnings[0]


def test_table_array_explode_fans_out_list_labels() -> None:
    result = toml_table_array(
        _context(
            {"pyproject.toml": MYPY_OVERRIDES},
            {"key": "tool.mypy.overrides", "label": "module", "explode": True},
        )
    )

    # foo.* (1) + [bar.baz, bar.qux] (2) + missing label (#3, 1) = 4
    assert result.value == 4
    assert [str(o) for o in result.occurrences] == [
        "pyproject.toml: foo.*",
        "pyproject.toml: bar.baz",
        "pyproject.toml: bar.qux",
        "pyproject.toml: #3",
    ]


def test_validate_table_array_params() -> None:
    ok = {"key": "tool.mypy.overrides", "label": "module"}
    assert validate_toml_table_array_params(ok) == []
    assert validate_toml_table_array_params({"key": ""}) == [
        "key must be a non-empty string"
    ]
    assert validate_toml_table_array_params({"key": "x", "label": 5}) == [
        "label must be a string"
    ]
    assert validate_toml_table_array_params({"key": "x", "explode": "yes"}) == [
        "explode must be a boolean"
    ]
    assert validate_toml_table_array_params({"key": "x", "explode": True}) == [
        "explode = true requires label"
    ]


def test_ini_list_length_splits_commas_and_newlines() -> None:
    result = ini_list_length(
        _context(
            {".pylintrc": PYLINTRC},
            {"file": ".pylintrc", "section": "MESSAGES CONTROL", "option": "disable"},
        )
    )

    assert result.value == 3
    assert result.warnings == ()
    assert [o.note for o in result.occurrences] == [
        "too-many-arguments",
        "missing-docstring",
        "invalid-name",
    ]


def test_ini_missing_file_warns() -> None:
    result = ini_list_length(
        _context({}, {"file": ".pylintrc", "section": "S", "option": "o"})
    )

    assert result.value == 0
    assert ".pylintrc: not found or unreadable" in result.warnings[0]


def test_ini_missing_section_warns() -> None:
    result = ini_list_length(
        _context(
            {".pylintrc": PYLINTRC},
            {"file": ".pylintrc", "section": "NOPE", "option": "disable"},
        )
    )

    assert result.value == 0
    assert 'section "NOPE" not found' in result.warnings[0]


def test_ini_missing_option_warns() -> None:
    result = ini_list_length(
        _context(
            {".pylintrc": PYLINTRC},
            {"file": ".pylintrc", "section": "FORMAT", "option": "disable"},
        )
    )

    assert result.value == 0
    assert 'option "disable" not found in "FORMAT"' in result.warnings[0]


def test_ini_malformed_warns() -> None:
    result = ini_list_length(
        _context(
            {".pylintrc": "no section header\nvalue = 1\n"},
            {"file": ".pylintrc", "section": "S", "option": "o"},
        )
    )

    assert result.value == 0
    assert "invalid INI" in result.warnings[0]


def test_validate_ini_params() -> None:
    assert validate_ini_params({"file": "a", "section": "b", "option": "c"}) == []
    assert validate_ini_params({"file": 1, "section": "b", "option": "c"}) == [
        "file must be a string"
    ]
