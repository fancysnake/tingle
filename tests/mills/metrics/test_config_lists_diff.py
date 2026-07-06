from typing import TYPE_CHECKING, Any

from tingle.mills.metrics.config_lists import (
    ini_list_length_diff,
    toml_list_length_diff,
)
from tingle.pacts.diff import DiffMetricContext

if TYPE_CHECKING:
    from collections.abc import Mapping


def _context(
    current: Mapping[str, str | None],
    base: Mapping[str, str | None],
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
        _context(current, base, {"key": "tool.ruff.lint.ignore"})
    )

    assert result.net == 2
    assert result.added is None
    assert result.removed is None
    assert dict(result.details) == {"base": 1, "current": 3}


def test_toml_negative_delta() -> None:
    base = {"pyproject.toml": '[tool.ruff.lint]\nignore = ["E501", "D203"]\n'}
    current = {"pyproject.toml": "[tool.ruff.lint]\nignore = []\n"}

    result = toml_list_length_diff(
        _context(current, base, {"key": "tool.ruff.lint.ignore"})
    )

    assert result.net == -2


def test_toml_missing_base_is_zero_with_warning() -> None:
    current = {"pyproject.toml": '[tool.ruff.lint]\nignore = ["E501"]\n'}

    result = toml_list_length_diff(
        _context(current, {}, {"key": "tool.ruff.lint.ignore"})
    )

    assert result.net == 1
    assert dict(result.details) == {"base": 0, "current": 1}
    assert any(
        warning.startswith("base side: pyproject.toml: not found")
        for warning in result.warnings
    )


def test_ini_delta() -> None:
    base = {".pylintrc": "[MESSAGES CONTROL]\ndisable = a,b\n"}
    current = {".pylintrc": "[MESSAGES CONTROL]\ndisable = a,b,c\n"}
    params = {
        "file": ".pylintrc",
        "section": "MESSAGES CONTROL",
        "option": "disable",
    }

    result = ini_list_length_diff(_context(current, base, params))

    assert result.net == 1
    assert dict(result.details) == {"base": 2, "current": 3}
