from __future__ import annotations

from tingle.mills.metrics.registry import METRIC_TYPES

EXPECTED_TYPES = {
    "regex_count",
    "symbol_uses",
    "toml_list_length",
    "toml_table_array",
    "ini_list_length",
    "file_count",
    "line_count",
}


def test_all_metric_types_are_registered() -> None:
    assert set(METRIC_TYPES) == EXPECTED_TYPES


def test_names_match_keys() -> None:
    for key, metric_type in METRIC_TYPES.items():
        assert metric_type.name == key
        assert metric_type.description


def test_param_specs() -> None:
    assert METRIC_TYPES["regex_count"].required_params == ("pattern",)
    assert METRIC_TYPES["regex_count"].primary_param == "pattern"
    assert METRIC_TYPES["symbol_uses"].required_params == ("symbol",)
    assert METRIC_TYPES["symbol_uses"].primary_param == "symbol"
    assert METRIC_TYPES["toml_list_length"].required_params == ("key",)
    assert METRIC_TYPES["toml_list_length"].optional_params == ("file",)
    assert METRIC_TYPES["toml_table_array"].required_params == ("key",)
    assert METRIC_TYPES["toml_table_array"].optional_params == (
        "file",
        "label",
        "explode",
    )
    assert METRIC_TYPES["toml_table_array"].primary_param == "key"
    assert METRIC_TYPES["ini_list_length"].required_params == (
        "file",
        "section",
        "option",
    )
    assert METRIC_TYPES["ini_list_length"].primary_param is None
    assert METRIC_TYPES["file_count"].required_params == ()
    assert METRIC_TYPES["line_count"].required_params == ()


def test_every_metric_type_has_a_diff_variant() -> None:
    for metric_type in METRIC_TYPES.values():
        assert metric_type.diff_func is not None, metric_type.name
