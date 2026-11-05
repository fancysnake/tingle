from __future__ import annotations

from pathlib import Path, PurePath
from unittest.mock import MagicMock

import pytest
from support import FakeProject

from tingle.mills.config import validate
from tingle.mills.services import ConfigService, MetricsService
from tingle.pacts.config import (
    BaseConfig,
    Config,
    ConfigError,
    ConfigNotFoundError,
    MetricDraft,
    MetricTemplate,
)
from tingle.pacts.metrics import MetricResult, MetricType
from tingle.specs.ranges import UNREACHABLE_DIRS

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


def _config_service(
    store: MagicMock, project_files: MagicMock | None = None
) -> ConfigService:
    return ConfigService(
        store=store,
        metric_types=METRIC_TYPES,
        templates=MagicMock(),
        project_files=project_files or MagicMock(),
    )


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


def test_write_starter_starts_on_the_tools_the_project_configures() -> None:
    store = MagicMock()
    store.write_starter.return_value = SOURCE
    project_files = MagicMock(return_value=FakeProject({"ty.toml": ""}))

    assert _config_service(store, project_files).write_starter(CWD) == SOURCE
    project_files.assert_called_once_with(CWD)
    store.write_starter.assert_called_once_with(
        CWD, ("tingle.builtins.ty.ignore_comment",)
    )
    store.write_examples.assert_not_called()


def test_write_starter_writes_the_examples_when_no_tool_is_known() -> None:
    store = MagicMock()
    store.write_examples.return_value = SOURCE
    project_files = MagicMock(return_value=FakeProject({"README.md": ""}))

    assert _config_service(store, project_files).write_starter(CWD) == SOURCE
    store.write_examples.assert_called_once_with(CWD)
    store.write_starter.assert_not_called()


def test_list_metric_types_orders_by_name() -> None:
    """The gate prints them straight out, so the order is settled here."""
    unordered = {
        name: MetricType(name=name, func=lambda _ctx: MetricResult(value=0))
        for name in ("regex_count", "file_count", "line_count")
    }
    service = ConfigService(
        store=MagicMock(),
        metric_types=unordered,
        templates=MagicMock(),
        project_files=MagicMock(),
    )

    names = [metric_type.name for metric_type in service.list_metric_types()]

    assert names == ["file_count", "line_count", "regex_count"]


def _config() -> Config:
    return validate(RAW, METRIC_TYPES, source=SOURCE)


def test_run_anchors_the_project_files_at_the_config_root() -> None:
    project_files = MagicMock()
    project_files.return_value.walk.return_value = ()
    service = MetricsService(
        project_files=project_files,
        diff_source=MagicMock(),
        metric_types=METRIC_TYPES,
        configs=MagicMock(),
    )

    report = service.run(_config())

    project_files.assert_called_once_with(CWD, prune=UNREACHABLE_DIRS)
    assert [outcome.spec.name for outcome in report.outcomes] == ["files"]


def test_diff_anchors_both_adapters_at_the_config_root() -> None:
    project_files = MagicMock()
    project_files.return_value.walk.return_value = ()
    diff_source = MagicMock()
    diff_source.return_value.branch_diff.return_value.files = ()
    service = MetricsService(
        project_files=project_files,
        diff_source=diff_source,
        metric_types=METRIC_TYPES,
        configs=MagicMock(),
    )

    service.diff(_config(), "main")

    project_files.assert_called_once_with(CWD, prune=UNREACHABLE_DIRS)
    diff_source.assert_called_once_with(CWD)
    diff_source.return_value.branch_diff.assert_called_once_with("main")


def _at_base(store: MagicMock, templates: MagicMock | None = None) -> ConfigService:
    return ConfigService(
        store=store,
        metric_types=METRIC_TYPES,
        templates=templates or MagicMock(),
        project_files=MagicMock(),
    )


def test_at_base_says_when_there_is_no_config() -> None:
    store = MagicMock()
    store.load_at.return_value = None

    found = _at_base(store).at_base(_config(), MagicMock())

    assert found == BaseConfig(problem="the base has no config")


def test_at_base_says_when_the_config_cannot_be_parsed() -> None:
    store = MagicMock()
    store.load_at.side_effect = ConfigError(["bad"])

    found = _at_base(store).at_base(_config(), MagicMock())

    assert found == BaseConfig(problem="the base config cannot be parsed")


def test_at_base_remembers_strict_on_a_config_that_no_longer_validates() -> None:
    store = MagicMock()
    raw = {"check": {"strict": True}, "metrics": [{"name": "gone", "type": "x"}]}
    store.load_at.return_value = (PurePath("tingle.toml"), raw)

    found = _at_base(store).at_base(_config(), MagicMock())

    assert found.config is None
    assert found.problem == "the base config does not validate"
    assert found.asked


def test_at_base_lists_only_the_modules_inside_the_project(tmp_path: Path) -> None:
    store = MagicMock()
    store.load_at.return_value = (
        PurePath("tingle.toml"),
        {
            **RAW,
            "check": {"strict": True},
            "templates": {"a": {"base": "in.t"}, "b": {"base": "out.t"}},
        },
    )
    templates = MagicMock()
    templates.load.return_value = MetricTemplate()
    templates.module_file.side_effect = lambda path: (
        tmp_path / "pack.py" if path == "in.t" else Path("/elsewhere/out.py")
    )
    config = validate(RAW, METRIC_TYPES, source=tmp_path / "tingle.toml")

    found = _at_base(store, templates).at_base(config, MagicMock())

    assert found.modules == (PurePath("pack.py"),)
    assert found.source == PurePath("tingle.toml")


def test_at_base_resolves_nothing_when_neither_side_asks_for_strict() -> None:
    store = MagicMock()
    store.load_at.return_value = (PurePath("tingle.toml"), RAW)
    templates = MagicMock()

    found = _at_base(store, templates).at_base(_config(), MagicMock())

    assert found == BaseConfig()
    templates.load.assert_not_called()
