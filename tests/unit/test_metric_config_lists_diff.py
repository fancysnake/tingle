from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tingle.mills.metrics.config_lists import (
    ini_list_length_diff,
    toml_list_length_diff,
    toml_table_array_diff,
)
from tingle.pacts.diff import DiffMetricContext

if TYPE_CHECKING:
    from collections.abc import Mapping


def _context(
    current: Mapping[str, str | None],
    base: Mapping[str, str | None],
    *,
    params: Mapping[str, Any],
) -> DiffMetricContext:
    return DiffMetricContext(
        files=(),
        read=lambda path: current.get(str(path)),
        read_base=lambda path: base.get(str(path)),
        params=params,
    )


def test_toml_delta_between_base_and_current() -> None:
    base = {"pyproject.toml": '[tool.ruff.lint]\nignore = ["E501"]\n'}
    current = {
        "pyproject.toml": '[tool.ruff.lint]\nignore = ["E501", "D203", "ANN101"]\n'
    }

    result = toml_list_length_diff(
        _context(current, base, params={"key": "tool.ruff.lint.ignore"})
    )

    assert result.net == 2
    assert result.added is None
    assert result.removed is None
    assert dict(result.details) == {"base": 1, "current": 3}
    assert [o.note for o in result.added_occurrences] == ["D203", "ANN101"]
    assert not result.removed_occurrences


def test_toml_negative_delta() -> None:
    base = {"pyproject.toml": '[tool.ruff.lint]\nignore = ["E501", "D203"]\n'}
    current = {"pyproject.toml": "[tool.ruff.lint]\nignore = []\n"}

    result = toml_list_length_diff(
        _context(current, base, params={"key": "tool.ruff.lint.ignore"})
    )

    assert result.net == -2
    assert [o.note for o in result.removed_occurrences] == ["E501", "D203"]


def test_swapped_entries_show_both_sides() -> None:
    base = {"pyproject.toml": '[tool.ruff.lint]\nignore = ["E501", "ANN101"]\n'}
    current = {"pyproject.toml": '[tool.ruff.lint]\nignore = ["E501", "D419"]\n'}

    result = toml_list_length_diff(
        _context(current, base, params={"key": "tool.ruff.lint.ignore"})
    )

    assert result.net == 0
    assert [o.note for o in result.added_occurrences] == ["D419"]
    assert [o.note for o in result.removed_occurrences] == ["ANN101"]


def test_duplicate_entries_document_net_vs_set_mismatch() -> None:
    base = {"pyproject.toml": '[tool.ruff.lint]\nignore = ["E501"]\n'}
    current = {"pyproject.toml": '[tool.ruff.lint]\nignore = ["E501", "E501"]\n'}

    result = toml_list_length_diff(
        _context(current, base, params={"key": "tool.ruff.lint.ignore"})
    )

    assert result.net == 1  # count-based
    assert not result.added_occurrences  # set-based: no new distinct entry


def test_toml_missing_base_is_zero_with_warning() -> None:
    current = {"pyproject.toml": '[tool.ruff.lint]\nignore = ["E501"]\n'}

    result = toml_list_length_diff(
        _context(current, {}, params={"key": "tool.ruff.lint.ignore"})
    )

    assert result.net == 1
    assert dict(result.details) == {"base": 0, "current": 1}
    assert any(
        warning.startswith("base side: pyproject.toml: not found")
        for warning in result.warnings
    )


def _overrides(*modules: str) -> str:
    return "".join(
        f'[[tool.mypy.overrides]]\nmodule = "{module}"\n\n' for module in modules
    )


def test_table_array_delta_added_and_removed() -> None:
    base = {"pyproject.toml": _overrides("foo.*", "bar.*")}
    current = {"pyproject.toml": _overrides("foo.*", "baz.*")}
    params = {"key": "tool.mypy.overrides", "label": "module"}

    result = toml_table_array_diff(_context(current, base, params=params))

    assert result.net == 0
    assert [o.note for o in result.added_occurrences] == ["baz.*"]
    assert [o.note for o in result.removed_occurrences] == ["bar.*"]


def test_table_array_missing_base_prefixes_warning() -> None:
    current = {"pyproject.toml": _overrides("foo.*")}
    params = {"key": "tool.mypy.overrides", "label": "module"}

    result = toml_table_array_diff(_context(current, {}, params=params))

    assert result.net == 1
    assert any(
        warning.startswith("base side: pyproject.toml: not found")
        for warning in result.warnings
    )


def test_ini_delta() -> None:
    base = {".pylintrc": "[MESSAGES CONTROL]\ndisable = a,b\n"}
    current = {".pylintrc": "[MESSAGES CONTROL]\ndisable = a,b,c\n"}
    params = {"file": ".pylintrc", "section": "MESSAGES CONTROL", "option": "disable"}

    result = ini_list_length_diff(_context(current, base, params=params))

    assert result.net == 1
    assert dict(result.details) == {"base": 2, "current": 3}
