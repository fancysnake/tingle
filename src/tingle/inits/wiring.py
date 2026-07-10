"""Static wiring: the metric-type table, config loading/editing, project IO."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tingle.links.config_file.toml import TomlConfigStore
from tingle.links.fs.local import LocalProjectFiles
from tingle.links.git.cli import GitCli
from tingle.mills.config import validate
from tingle.mills.metrics.registry import METRIC_TYPES
from tingle.pacts.config import Config, ConfigNotFoundError

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from tingle.pacts.diff import DiffSource
    from tingle.pacts.metrics import ProjectFiles

__all__ = [
    "METRIC_TYPES",
    "append_metric_to",
    "config_edit_target",
    "diff_source",
    "load_config",
    "load_raw_config",
    "project_files",
    "write_starter_config",
]

_STORE = TomlConfigStore()


def project_files(root: Path) -> ProjectFiles:
    """Build the filesystem view metrics read from."""
    return LocalProjectFiles(root)


def diff_source(root: Path) -> DiffSource:
    """Build the branch-diff provider (git) anchored at the project root."""
    return GitCli(root)


def load_config(cwd: Path, override: Path | None = None) -> Config:
    """Discover, parse, and validate the tingle configuration."""
    source, raw = _STORE.load_raw(cwd, override)
    resolved = source.resolve()
    return validate(raw, METRIC_TYPES, root=resolved.parent, source=resolved)


def load_raw_config(cwd: Path) -> dict[str, Any]:
    """Raw config data for editing flows; empty when no config exists yet."""
    try:
        return _STORE.load_raw(cwd)[1]
    except ConfigNotFoundError:
        return {}


def config_edit_target(cwd: Path) -> Path:
    """Return the config file `tingle add` should write to."""
    return _STORE.edit_target(cwd)


def append_metric_to(path: Path, metric: Mapping[str, Any]) -> None:
    """Append a metric table to the config file, preserving formatting."""
    _STORE.append_metric(path, metric)


def write_starter_config(cwd: Path) -> Path:
    """Create the starter tingle.toml; raises FileExistsError if present."""
    return _STORE.write_starter(cwd)
