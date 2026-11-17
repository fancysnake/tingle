from __future__ import annotations

from typing import TYPE_CHECKING

from tingle.inits.services import Services
from tingle.links.config_file.toml import TomlConfigStore
from tingle.links.fs.local import LocalProjectFiles
from tingle.links.git.cli import GitCli
from tingle.mills.metrics.registry import METRIC_TYPES
from tingle.pacts.services import (
    BrowseServiceProtocol,
    ConfigServiceProtocol,
    MetricsServiceProtocol,
    ServicesProtocol,
    SkillServiceProtocol,
)

if TYPE_CHECKING:
    from pathlib import Path

SERVICE_PROTOCOLS = {
    "config": ConfigServiceProtocol,
    "metrics": MetricsServiceProtocol,
    "skill": SkillServiceProtocol,
    "browse": BrowseServiceProtocol,
}


def test_config_service_is_backed_by_the_toml_store() -> None:
    config = Services().config

    assert isinstance(config.store, TomlConfigStore)
    assert config.metric_types is METRIC_TYPES


def test_metrics_service_builds_the_local_and_git_adapters(tmp_path: Path) -> None:
    metrics = Services().metrics

    assert isinstance(metrics.project_files(tmp_path), LocalProjectFiles)
    assert isinstance(metrics.diff_source(tmp_path), GitCli)
    assert metrics.metric_types is METRIC_TYPES


def test_service_leaves_are_cached_per_container() -> None:
    services = Services()
    config, metrics = services.config, services.metrics

    assert services.config is config
    assert services.metrics is metrics
    assert Services().config is not config


def test_services_provide_every_method_the_gate_protocols_ask_for() -> None:
    services = Services()

    assert set(SERVICE_PROTOCOLS) < ServicesProtocol.__abstractmethods__
    for name, protocol in SERVICE_PROTOCOLS.items():
        service = getattr(services, name)
        missing = {m for m in protocol.__abstractmethods__ if not hasattr(service, m)}
        assert not missing, f"{name} lacks {missing}"
