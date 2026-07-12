from __future__ import annotations

import pytest

from tingle.mills.add import build_metric
from tingle.mills.metrics.registry import METRIC_TYPES
from tingle.pacts.config import ConfigError, MetricDraft

RAW = {
    "ranges": {"python": {"include": ["**/*.py"]}},
    "metrics": [{"name": "noqa-comments", "type": "regex_count", "pattern": "# noqa"}],
}


def test_builds_metric_with_auto_name() -> None:
    draft = MetricDraft(type_name="regex_count", value=r"#\s*noqa")

    metric = build_metric(RAW, METRIC_TYPES, draft=draft)

    assert metric["name"] == "regex_count-s-noqa"
    assert metric["type"] == "regex_count"
    assert metric["pattern"] == r"#\s*noqa"


def test_single_range_uses_string_key() -> None:
    draft = MetricDraft(type_name="regex_count", value="x", ranges=("python",))

    metric = build_metric(RAW, METRIC_TYPES, draft=draft)

    assert metric["range"] == "python"
    assert "ranges" not in metric


def test_multiple_ranges_use_list_key() -> None:
    raw = {"ranges": {"a": {"include": ["**/*.a"]}, "b": {"include": ["**/*.b"]}}}
    draft = MetricDraft(type_name="regex_count", value="x", ranges=("a", "b"))

    metric = build_metric(raw, METRIC_TYPES, draft=draft)

    assert metric["ranges"] == ["a", "b"]


def test_auto_name_deduplicates() -> None:
    raw = {
        "metrics": [
            {"name": "file_count", "type": "file_count"},
            {"name": "file_count-2", "type": "file_count"},
        ]
    }

    metric = build_metric(raw, METRIC_TYPES, draft=MetricDraft(type_name="file_count"))

    assert metric["name"] == "file_count-3"


def test_explicit_name_and_params() -> None:
    draft = MetricDraft(
        type_name="ini_list_length",
        name="pylint-disables",
        params={
            "file": ".pylintrc",
            "section": "MESSAGES CONTROL",
            "option": "disable",
        },
    )

    metric = build_metric({}, METRIC_TYPES, draft=draft)

    assert metric["name"] == "pylint-disables"
    assert metric["section"] == "MESSAGES CONTROL"


def test_group_is_written_after_type_and_validates() -> None:
    draft = MetricDraft(type_name="regex_count", value="x", group="typing")

    metric = build_metric(RAW, METRIC_TYPES, draft=draft)

    assert metric["group"] == "typing"
    # emitted before params for a readable diff: name, type, group, then key
    assert list(metric)[:3] == ["name", "type", "group"]


def test_no_group_omits_the_key() -> None:
    metric = build_metric(
        RAW, METRIC_TYPES, draft=MetricDraft(type_name="regex_count", value="x")
    )

    assert "group" not in metric


def test_toml_table_array_can_be_added() -> None:
    draft = MetricDraft(
        type_name="toml_table_array",
        value="tool.mypy.overrides",
        params={"label": "module"},
    )

    metric = build_metric({}, METRIC_TYPES, draft=draft)

    assert metric["type"] == "toml_table_array"
    assert metric["key"] == "tool.mypy.overrides"
    assert metric["label"] == "module"


def test_unknown_type_is_rejected() -> None:
    with pytest.raises(ConfigError) as excinfo:
        build_metric({}, METRIC_TYPES, draft=MetricDraft(type_name="nope"))

    assert "unknown metric type 'nope'" in excinfo.value.errors[0]


def test_positional_value_requires_primary_param() -> None:
    with pytest.raises(ConfigError) as excinfo:
        build_metric(
            {}, METRIC_TYPES, draft=MetricDraft(type_name="file_count", value="x")
        )

    assert "takes no positional value" in excinfo.value.errors[0]


def test_invalid_pattern_is_rejected() -> None:
    with pytest.raises(ConfigError) as excinfo:
        build_metric(
            {}, METRIC_TYPES, draft=MetricDraft(type_name="regex_count", value="(")
        )

    assert any("invalid pattern" in error for error in excinfo.value.errors)


def test_unknown_range_is_rejected() -> None:
    draft = MetricDraft(type_name="regex_count", value="x", ranges=("nope",))

    with pytest.raises(ConfigError) as excinfo:
        build_metric({}, METRIC_TYPES, draft=draft)

    assert any('unknown range "nope"' in error for error in excinfo.value.errors)


def test_duplicate_explicit_name_is_rejected() -> None:
    draft = MetricDraft(type_name="regex_count", value="x", name="noqa-comments")

    with pytest.raises(ConfigError) as excinfo:
        build_metric(RAW, METRIC_TYPES, draft=draft)

    assert any("duplicate name" in error for error in excinfo.value.errors)


def test_value_and_param_conflict() -> None:
    draft = MetricDraft(type_name="regex_count", value="x", params={"pattern": "y"})

    with pytest.raises(ConfigError) as excinfo:
        build_metric({}, METRIC_TYPES, draft=draft)

    assert "both positionally and via --param" in excinfo.value.errors[0]
