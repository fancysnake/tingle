from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from tingle.mills.config import validate
from tingle.pacts.config import Config, ConfigError
from tingle.pacts.metrics import MetricContext, MetricResult, MetricType
from tingle.specs.config import IMPLICIT_RANGE_INCLUDE, IMPLICIT_RANGE_NAME

if TYPE_CHECKING:
    from collections.abc import Mapping

ROOT = Path("/proj")
SOURCE = Path("/proj/tingle.toml")


def _noop(_: MetricContext) -> MetricResult:
    return MetricResult(value=0)


def _reject_broken_pattern(params: Mapping[str, Any]) -> list[str]:
    if params.get("pattern") == "(":
        return ["pattern does not compile"]
    return []


METRIC_TYPES = {
    "regex_count": MetricType(
        name="regex_count",
        func=_noop,
        required_params=("pattern",),
        optional_params=("flags",),
        validate_params=_reject_broken_pattern,
    ),
    "file_count": MetricType(name="file_count", func=_noop),
}


def _validate(raw: Mapping[str, Any]) -> Config:
    return validate(raw, METRIC_TYPES, root=ROOT, source=SOURCE)


def _errors_of(raw: Mapping[str, Any]) -> list[str]:
    with pytest.raises(ConfigError) as excinfo:
        _validate(raw)
    return excinfo.value.errors


def test_valid_config() -> None:
    config = _validate(
        {
            "ranges": {
                "python": {
                    "include": ["src/**/*.py"],
                    "exclude": ["src/gen/**"],
                    "default": True,
                },
                "js": {"include": ["web/**/*.js"]},
            },
            "metrics": [
                {
                    "name": "noqa",
                    "type": "regex_count",
                    "range": "python",
                    "pattern": "# noqa",
                },
                {
                    "name": "todo",
                    "type": "regex_count",
                    "ranges": ["python", "js"],
                    "pattern": "TODO",
                },
                {"name": "files", "type": "file_count"},
            ],
        }
    )

    assert config.root == ROOT
    assert config.source == SOURCE
    assert config.ranges["python"].exclude == ("src/gen/**",)
    assert config.default_range.name == "python"
    noqa, todo, files = config.metrics
    assert noqa.ranges == ("python",)
    assert dict(noqa.params) == {"pattern": "# noqa"}
    assert todo.ranges == ("python", "js")
    assert files.ranges == ()


def test_no_default_falls_back_to_implicit_all_files() -> None:
    config = _validate({"metrics": []})

    assert config.default_range.name == IMPLICIT_RANGE_NAME
    assert config.default_range.include == IMPLICIT_RANGE_INCLUDE


def test_errors_are_aggregated() -> None:
    errors = _errors_of(
        {
            "typo_section": {},
            "ranges": {"python": {"default": "yes"}},
            "metrics": [
                {"name": "bad name!", "type": "regex_count", "pattern": "x"},
                {"name": "no-type"},
            ],
        }
    )

    assert 'unknown top-level key "typo_section"' in errors
    assert 'range "python": missing include' in errors
    assert 'range "python": default must be a boolean' in errors
    assert (
        'metric "bad name!": invalid name '
        "(allowed: letters, digits, '_', '-', '.')" in errors
    )
    assert 'metric "no-type": missing type' in errors


def test_duplicate_metric_names() -> None:
    errors = _errors_of(
        {
            "metrics": [
                {"name": "twice", "type": "file_count"},
                {"name": "twice", "type": "file_count"},
            ]
        }
    )

    assert 'metric "twice": duplicate name' in errors


def test_unknown_type() -> None:
    errors = _errors_of({"metrics": [{"name": "x", "type": "nope"}]})

    assert "metric \"x\": unknown type 'nope'" in errors


def test_unknown_range_reference() -> None:
    errors = _errors_of(
        {
            "metrics": [
                {"name": "x", "type": "file_count", "range": "missing"},
            ]
        }
    )

    assert 'metric "x": unknown range "missing"' in errors


def test_range_and_ranges_conflict() -> None:
    errors = _errors_of(
        {
            "ranges": {"python": {"include": ["**/*.py"]}},
            "metrics": [
                {
                    "name": "x",
                    "type": "file_count",
                    "range": "python",
                    "ranges": ["python"],
                }
            ],
        }
    )

    assert 'metric "x": give either "range" or "ranges", not both' in errors


def test_empty_ranges_list() -> None:
    errors = _errors_of(
        {"metrics": [{"name": "x", "type": "file_count", "ranges": []}]}
    )

    assert 'metric "x": ranges must not be empty' in errors


def test_multiple_default_ranges() -> None:
    errors = _errors_of(
        {
            "ranges": {
                "a": {"include": ["**/*.a"], "default": True},
                "b": {"include": ["**/*.b"], "default": True},
            }
        }
    )

    assert "only one range may set default = true (found: a, b)" in errors


def test_missing_required_param() -> None:
    errors = _errors_of({"metrics": [{"name": "x", "type": "regex_count"}]})

    assert 'metric "x": missing required param "pattern"' in errors


def test_unknown_param() -> None:
    errors = _errors_of(
        {
            "metrics": [
                {"name": "x", "type": "regex_count", "pattern": "a", "patern": "b"}
            ]
        }
    )

    assert 'metric "x": unknown param "patern"' in errors


def test_validate_params_hook_reports_problems() -> None:
    errors = _errors_of(
        {"metrics": [{"name": "x", "type": "regex_count", "pattern": "("}]}
    )

    assert 'metric "x": pattern does not compile' in errors


def test_metrics_must_be_an_array() -> None:
    errors = _errors_of({"metrics": {"name": "x"}})

    assert "[[metrics]] must be an array of tables" in errors


def test_include_must_be_string_list() -> None:
    errors = _errors_of({"ranges": {"python": {"include": [1, 2]}}})

    assert 'range "python": include must be a list of strings' in errors


def test_diff_base_defaults_to_none() -> None:
    config = _validate({"metrics": []})

    assert config.diff_base is None


def test_diff_base_is_read() -> None:
    config = _validate({"diff": {"base": "origin/develop"}, "metrics": []})

    assert config.diff_base == "origin/develop"


def test_diff_unknown_key() -> None:
    errors = _errors_of({"diff": {"branch": "main"}})

    assert '[diff]: unknown key "branch"' in errors


def test_diff_base_must_be_string() -> None:
    errors = _errors_of({"diff": {"base": 5}})

    assert "[diff]: base must be a string" in errors


def test_diff_must_be_table() -> None:
    errors = _errors_of({"diff": "main"})

    assert "[diff] must be a table" in errors
