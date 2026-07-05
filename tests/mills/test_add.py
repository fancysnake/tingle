import pytest

from tingle.inits.wiring import METRIC_TYPES
from tingle.mills.add import build_metric
from tingle.pacts.config import ConfigError

RAW = {
    "ranges": {"python": {"include": ["**/*.py"]}},
    "metrics": [
        {"name": "noqa-comments", "type": "regex_count", "pattern": "# noqa"}
    ],
}


def test_builds_metric_with_auto_name() -> None:
    metric = build_metric(RAW, METRIC_TYPES, "regex_count", value=r"#\s*noqa")

    assert metric["name"] == "regex_count-s-noqa"
    assert metric["type"] == "regex_count"
    assert metric["pattern"] == r"#\s*noqa"


def test_single_range_uses_string_key() -> None:
    metric = build_metric(
        RAW, METRIC_TYPES, "regex_count", value="x", ranges=["python"]
    )

    assert metric["range"] == "python"
    assert "ranges" not in metric


def test_multiple_ranges_use_list_key() -> None:
    raw = {
        "ranges": {
            "a": {"include": ["**/*.a"]},
            "b": {"include": ["**/*.b"]},
        }
    }

    metric = build_metric(
        raw, METRIC_TYPES, "regex_count", value="x", ranges=["a", "b"]
    )

    assert metric["ranges"] == ["a", "b"]


def test_auto_name_deduplicates() -> None:
    raw = {
        "metrics": [
            {"name": "file_count", "type": "file_count"},
            {"name": "file_count-2", "type": "file_count"},
        ]
    }

    metric = build_metric(raw, METRIC_TYPES, "file_count")

    assert metric["name"] == "file_count-3"


def test_explicit_name_and_params() -> None:
    metric = build_metric(
        {},
        METRIC_TYPES,
        "ini_list_length",
        name="pylint-disables",
        params={
            "file": ".pylintrc",
            "section": "MESSAGES CONTROL",
            "option": "disable",
        },
    )

    assert metric["name"] == "pylint-disables"
    assert metric["section"] == "MESSAGES CONTROL"


def test_unknown_type_is_rejected() -> None:
    with pytest.raises(ConfigError) as excinfo:
        build_metric({}, METRIC_TYPES, "nope")

    assert "unknown metric type 'nope'" in excinfo.value.errors[0]


def test_positional_value_requires_primary_param() -> None:
    with pytest.raises(ConfigError) as excinfo:
        build_metric({}, METRIC_TYPES, "file_count", value="x")

    assert "takes no positional value" in excinfo.value.errors[0]


def test_invalid_pattern_is_rejected() -> None:
    with pytest.raises(ConfigError) as excinfo:
        build_metric({}, METRIC_TYPES, "regex_count", value="(")

    assert any("invalid pattern" in error for error in excinfo.value.errors)


def test_unknown_range_is_rejected() -> None:
    with pytest.raises(ConfigError) as excinfo:
        build_metric({}, METRIC_TYPES, "regex_count", value="x", ranges=["nope"])

    assert any('unknown range "nope"' in error for error in excinfo.value.errors)


def test_duplicate_explicit_name_is_rejected() -> None:
    with pytest.raises(ConfigError) as excinfo:
        build_metric(
            RAW, METRIC_TYPES, "regex_count", value="x", name="noqa-comments"
        )

    assert any("duplicate name" in error for error in excinfo.value.errors)


def test_value_and_param_conflict() -> None:
    with pytest.raises(ConfigError) as excinfo:
        build_metric(
            {}, METRIC_TYPES, "regex_count", value="x", params={"pattern": "y"}
        )

    assert "both positionally and via --param" in excinfo.value.errors[0]
