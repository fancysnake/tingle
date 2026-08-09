from __future__ import annotations

from tingle.mills.metrics.regex_count import regex_spread, regex_spread_diff
from tingle.mills.metrics.registry import METRIC_TYPES
from tingle.mills.metrics.symbol_uses import symbol_spread, symbol_spread_diff

EXPECTED_TYPES = {
    "regex_count",
    "regex_spread",
    "symbol_uses",
    "symbol_spread",
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
    assert METRIC_TYPES["regex_count"].params.required == ("pattern",)
    assert METRIC_TYPES["regex_count"].params.primary == "pattern"
    assert METRIC_TYPES["symbol_uses"].params.required == ("symbol",)
    assert METRIC_TYPES["symbol_uses"].params.primary == "symbol"
    assert METRIC_TYPES["regex_spread"].params.required == ("pattern",)
    assert METRIC_TYPES["regex_spread"].params.primary == "pattern"
    assert METRIC_TYPES["symbol_spread"].params.required == ("symbol",)
    assert METRIC_TYPES["symbol_spread"].params.primary == "symbol"
    assert METRIC_TYPES["toml_list_length"].params.required == ("key",)
    assert METRIC_TYPES["toml_list_length"].params.optional == ("file",)
    assert METRIC_TYPES["toml_table_array"].params.required == ("key",)
    assert METRIC_TYPES["toml_table_array"].params.optional == (
        "file",
        "label",
        "explode",
    )
    assert METRIC_TYPES["toml_table_array"].params.primary == "key"
    assert METRIC_TYPES["ini_list_length"].params.required == (
        "file",
        "section",
        "option",
    )
    assert METRIC_TYPES["ini_list_length"].params.primary is None
    assert not METRIC_TYPES["file_count"].params.required
    assert not METRIC_TYPES["line_count"].params.required


def test_every_metric_type_has_a_diff_variant() -> None:
    for metric_type in METRIC_TYPES.values():
        assert metric_type.diff_func is not None, metric_type.name


def test_spread_types_accept_what_their_counting_siblings_do() -> None:
    # a spread metric is the same search read differently, so anything
    # configurable on the count must be configurable on the spread
    for counting, spread in (
        ("regex_count", "regex_spread"),
        ("symbol_uses", "symbol_spread"),
    ):
        assert METRIC_TYPES[spread].params.optional == (
            METRIC_TYPES[counting].params.optional
        )
        assert METRIC_TYPES[spread].params.validate is (
            METRIC_TYPES[counting].params.validate
        )


def test_spread_types_are_wired_to_their_own_handlers() -> None:
    # the table is data, so a copy-paste slip would silently point a spread
    # type at its sibling's function and nothing else would notice
    for name, func, diff_func in (
        ("regex_spread", regex_spread, regex_spread_diff),
        ("symbol_spread", symbol_spread, symbol_spread_diff),
    ):
        assert METRIC_TYPES[name].func is func
        assert METRIC_TYPES[name].diff_func is diff_func
