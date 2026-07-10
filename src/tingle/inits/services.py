"""The composition root: builds the service graph gates are handed."""

from __future__ import annotations

from functools import cached_property

from tingle.links.config_file.toml import TomlConfigStore
from tingle.links.fs.local import LocalProjectFiles
from tingle.links.git.cli import GitCli
from tingle.mills.metrics.registry import METRIC_TYPES
from tingle.mills.services import ConfigService, MetricsService


class Services:
    """Every service a gate may reach, built on demand."""

    @cached_property
    def config(self) -> ConfigService:
        """Configuration discovery and editing, backed by the TOML store."""
        return ConfigService(store=TomlConfigStore(), metric_types=METRIC_TYPES)

    @cached_property
    def metrics(self) -> MetricsService:
        """Metric execution, backed by the local tree and the git CLI."""
        return MetricsService(
            project_files=LocalProjectFiles,
            diff_source=GitCli,
            metric_types=METRIC_TYPES,
        )
