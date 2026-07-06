"""Static wiring: the metric-type table, config loading/editing, project IO."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tingle.links.config_file.toml import (
    append_metric,
    edit_target,
    load_raw,
    write_starter,
)
from tingle.links.fs.local import LocalProjectFiles
from tingle.links.git.cli import GitCli
from tingle.mills.config import validate
from tingle.mills.metrics.config_lists import (
    ini_list_length,
    ini_list_length_diff,
    toml_list_length,
    toml_list_length_diff,
    validate_ini_params,
    validate_toml_params,
)
from tingle.mills.metrics.counts import (
    file_count,
    file_count_diff,
    line_count,
    line_count_diff,
)
from tingle.mills.metrics.regex_count import (
    regex_count,
    regex_count_diff,
)
from tingle.mills.metrics.regex_count import (
    validate_params as validate_regex_params,
)
from tingle.mills.metrics.symbol_uses import (
    symbol_uses,
    symbol_uses_diff,
)
from tingle.mills.metrics.symbol_uses import (
    validate_params as validate_symbol_params,
)
from tingle.pacts.config import Config, ConfigNotFoundError
from tingle.pacts.metrics import MetricType, ProjectFiles

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from tingle.pacts.diff import DiffSource

METRIC_TYPES: dict[str, MetricType] = {
    "regex_count": MetricType(
        name="regex_count",
        func=regex_count,
        required_params=("pattern",),
        optional_params=("flags",),
        primary_param="pattern",
        validate_params=validate_regex_params,
        description="Count regex matches in the files of the metric's ranges.",
        diff_func=regex_count_diff,
    ),
    "symbol_uses": MetricType(
        name="symbol_uses",
        func=symbol_uses,
        required_params=("symbol",),
        primary_param="symbol",
        validate_params=validate_symbol_params,
        description="Count references to a function or class in Python files.",
        diff_func=symbol_uses_diff,
    ),
    "toml_list_length": MetricType(
        name="toml_list_length",
        func=toml_list_length,
        required_params=("key",),
        optional_params=("file",),
        primary_param="key",
        validate_params=validate_toml_params,
        description="Length of the list at a dotted key in a TOML file.",
        diff_func=toml_list_length_diff,
    ),
    "ini_list_length": MetricType(
        name="ini_list_length",
        func=ini_list_length,
        required_params=("file", "section", "option"),
        validate_params=validate_ini_params,
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


def project_files(root: Path) -> ProjectFiles:
    """Build the filesystem view metrics read from."""
    return LocalProjectFiles(root)


def diff_source(root: Path) -> DiffSource:
    """Build the branch-diff provider (git) anchored at the project root."""
    return GitCli(root)


def load_config(cwd: Path, override: Path | None = None) -> Config:
    """Discover, parse, and validate the tingle configuration."""
    source, raw = load_raw(cwd, override)
    resolved = source.resolve()
    return validate(raw, METRIC_TYPES, root=resolved.parent, source=resolved)


def load_raw_config(cwd: Path) -> dict[str, Any]:
    """Raw config data for editing flows; empty when no config exists yet."""
    try:
        return load_raw(cwd)[1]
    except ConfigNotFoundError:
        return {}


def config_edit_target(cwd: Path) -> Path:
    """Return the config file `tingle add` should write to."""
    return edit_target(cwd)


def append_metric_to(path: Path, metric: Mapping[str, Any]) -> None:
    """Append a metric table to the config file, preserving formatting."""
    append_metric(path, metric)


def write_starter_config(cwd: Path) -> Path:
    """Create the starter tingle.toml; raises FileExistsError if present."""
    return write_starter(cwd)
