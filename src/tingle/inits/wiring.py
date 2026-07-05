"""Static wiring: the metric-type table and project IO construction."""

from pathlib import Path

from tingle.links.fs.local import LocalProjectFiles
from tingle.mills.metrics.config_lists import (
    ini_list_length,
    toml_list_length,
    validate_ini_params,
    validate_toml_params,
)
from tingle.mills.metrics.counts import file_count, line_count
from tingle.mills.metrics.regex_count import (
    regex_count,
)
from tingle.mills.metrics.regex_count import (
    validate_params as validate_regex_params,
)
from tingle.mills.metrics.symbol_uses import (
    symbol_uses,
)
from tingle.mills.metrics.symbol_uses import (
    validate_params as validate_symbol_params,
)
from tingle.pacts.metrics import MetricType, ProjectFiles

METRIC_TYPES: dict[str, MetricType] = {
    "regex_count": MetricType(
        name="regex_count",
        func=regex_count,
        required_params=("pattern",),
        optional_params=("flags",),
        primary_param="pattern",
        validate_params=validate_regex_params,
        description="Count regex matches in the files of the metric's ranges.",
    ),
    "symbol_uses": MetricType(
        name="symbol_uses",
        func=symbol_uses,
        required_params=("symbol",),
        primary_param="symbol",
        validate_params=validate_symbol_params,
        description="Count references to a function or class in Python files.",
    ),
    "toml_list_length": MetricType(
        name="toml_list_length",
        func=toml_list_length,
        required_params=("key",),
        optional_params=("file",),
        primary_param="key",
        validate_params=validate_toml_params,
        description="Length of the list at a dotted key in a TOML file.",
    ),
    "ini_list_length": MetricType(
        name="ini_list_length",
        func=ini_list_length,
        required_params=("file", "section", "option"),
        validate_params=validate_ini_params,
        description="Number of entries in a comma/newline separated INI option.",
    ),
    "file_count": MetricType(
        name="file_count",
        func=file_count,
        description="Number of files in the metric's ranges.",
    ),
    "line_count": MetricType(
        name="line_count",
        func=line_count,
        description="Total number of lines in the files of the metric's ranges.",
    ),
}


def project_files(root: Path) -> ProjectFiles:
    return LocalProjectFiles(root)
