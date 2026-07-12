from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tingle.mills.config import validate
from tingle.mills.services import ConfigService, MetricsService
from tingle.pacts.config import Config, ConfigError, ConfigNotFoundError, MetricDraft
from tingle.pacts.metrics import MetricResult, MetricType

CWD = Path("/project")
SOURCE = Path("/project/tingle.toml")

METRIC_TYPES = {
    "file_count": MetricType(
        name="file_count",
        func=lambda _ctx: MetricResult(value=0),
        diff_func=MagicMock(),
    )
}

RAW = {
    "ranges": {"python": {"include": ["**/*.py"], "default": True}},
    "metrics": [{"name": "files", "type": "file_count"}],
}


def _config_service(store: MagicMock) -> ConfigService:
    return ConfigService(store=store, metric_types=METRIC_TYPES)


def test_load_validates_the_raw_config_against_the_resolved_source() -> None:
    store = MagicMock()
    store.load_raw.return_value = (SOURCE, RAW)

    config = _config_service(store).load(CWD)

    store.load_raw.assert_called_once_with(CWD, None)
    assert config.source == SOURCE
    assert config.root == SOURCE.parent
    assert [spec.name for spec in config.metrics] == ["files"]


def test_load_passes_the_override_through() -> None:
    store = MagicMock()
    store.load_raw.return_value = (SOURCE, RAW)
    override = Path("/project/custom.toml")

    _config_service(store).load(CWD, override)

    store.load_raw.assert_called_once_with(CWD, override)


def test_load_raw_returns_empty_when_no_config_exists() -> None:
    store = MagicMock()
    store.load_raw.side_effect = ConfigNotFoundError("nope")

    assert not _config_service(store).load_raw(CWD)


def test_add_metric_appends_to_the_edit_target_and_returns_the_name() -> None:
    store = MagicMock()
    store.load_raw.return_value = (SOURCE, RAW)
    store.edit_target.return_value = SOURCE
    draft = MetricDraft(type_name="file_count", name="more-files")

    target, name = _config_service(store).add_metric(CWD, draft)

    assert (target, name) == (SOURCE, "more-files")
    appended_path, appended = store.append_metric.call_args.args
    assert appended_path == SOURCE
    assert appended["name"] == "more-files"
    assert appended["type"] == "file_count"


def test_add_metric_writes_nothing_when_the_draft_is_invalid() -> None:
    store = MagicMock()
    store.load_raw.return_value = (SOURCE, RAW)
    draft = MetricDraft(type_name="no_such_type")

    with pytest.raises(ConfigError):
        _config_service(store).add_metric(CWD, draft)

    store.append_metric.assert_not_called()


def test_write_starter_delegates_to_the_store() -> None:
    store = MagicMock()
    store.write_starter.return_value = SOURCE

    assert _config_service(store).write_starter(CWD) == SOURCE
    store.write_starter.assert_called_once_with(CWD)


def _config() -> Config:
    return validate(RAW, METRIC_TYPES, root=CWD, source=SOURCE)


def test_run_anchors_the_project_files_at_the_config_root() -> None:
    project_files = MagicMock()
    project_files.return_value.walk.return_value = ()
    service = MetricsService(
        project_files=project_files, diff_source=MagicMock(), metric_types=METRIC_TYPES
    )

    report = service.run(_config())

    project_files.assert_called_once_with(CWD)
    assert [outcome.spec.name for outcome in report.outcomes] == ["files"]


def test_diff_anchors_both_adapters_at_the_config_root() -> None:
    project_files = MagicMock()
    project_files.return_value.walk.return_value = ()
    diff_source = MagicMock()
    diff_source.return_value.branch_diff.return_value.files = ()
    service = MetricsService(
        project_files=project_files, diff_source=diff_source, metric_types=METRIC_TYPES
    )

    service.diff(_config(), "main")

    project_files.assert_called_once_with(CWD)
    diff_source.assert_called_once_with(CWD)
    diff_source.return_value.branch_diff.assert_called_once_with("main")
