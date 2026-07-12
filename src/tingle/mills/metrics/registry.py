"""The metric-type table: every built-in metric, keyed by its config name."""

from __future__ import annotations

from tingle.mills.metrics.config_lists import (
    ini_list_length,
    ini_list_length_diff,
    toml_list_length,
    toml_list_length_diff,
    toml_table_array,
    toml_table_array_diff,
    validate_ini_params,
    validate_toml_params,
    validate_toml_table_array_params,
)
from tingle.mills.metrics.counts import (
    file_count,
    file_count_diff,
    line_count,
    line_count_diff,
)
from tingle.mills.metrics.regex_count import regex_count, regex_count_diff
from tingle.mills.metrics.regex_count import validate_params as validate_regex_params
from tingle.mills.metrics.symbol_uses import symbol_uses, symbol_uses_diff
from tingle.mills.metrics.symbol_uses import validate_params as validate_symbol_params
from tingle.pacts.metrics import MetricType, ParamSchema

METRIC_TYPES: dict[str, MetricType] = {
    "regex_count": MetricType(
        name="regex_count",
        func=regex_count,
        params=ParamSchema(
            required=("pattern",),
            optional=("flags", "ignore_lines"),
            primary="pattern",
            validate=validate_regex_params,
        ),
        description="Count regex matches in the files of the metric's ranges.",
        diff_func=regex_count_diff,
    ),
    "symbol_uses": MetricType(
        name="symbol_uses",
        func=symbol_uses,
        params=ParamSchema(
            required=("symbol",),
            optional=("ignore_lines",),
            primary="symbol",
            validate=validate_symbol_params,
        ),
        description="Count references to a function or class in Python files.",
        diff_func=symbol_uses_diff,
    ),
    "toml_list_length": MetricType(
        name="toml_list_length",
        func=toml_list_length,
        params=ParamSchema(
            required=("key",),
            optional=("file",),
            primary="key",
            validate=validate_toml_params,
        ),
        description="Length of the list at a dotted key in a TOML file.",
        diff_func=toml_list_length_diff,
    ),
    "toml_table_array": MetricType(
        name="toml_table_array",
        func=toml_table_array,
        params=ParamSchema(
            required=("key",),
            optional=("file", "label", "explode"),
            primary="key",
            validate=validate_toml_table_array_params,
        ),
        description="Count entries of a TOML array of tables (e.g. mypy overrides).",
        diff_func=toml_table_array_diff,
    ),
    "ini_list_length": MetricType(
        name="ini_list_length",
        func=ini_list_length,
        params=ParamSchema(
            required=("file", "section", "option"), validate=validate_ini_params
        ),
        description="Number of entries in a comma/newline separated INI option.",
        diff_func=ini_list_length_diff,
    ),
    "file_count": MetricType(
        name="file_count",
        func=file_count,
        description="Number of files in the metric's ranges.",
        diff_func=file_count_diff,
    ),
    "line_count": MetricType(
        name="line_count",
        func=line_count,
        description="Total number of lines in the files of the metric's ranges.",
        diff_func=line_count_diff,
    ),
}
