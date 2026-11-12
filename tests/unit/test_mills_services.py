from __future__ import annotations

from dataclasses import replace
from pathlib import Path, PurePath
from unittest.mock import MagicMock

import pytest
from support import FakeProject

from tingle.mills.config import validate
from tingle.mills.services import ConfigService, MetricsService
from tingle.pacts.check import StrictVerdict
from tingle.pacts.config import (
    BaseConfigError,
    Config,
    ConfigError,
    ConfigNotFoundError,
    MetricDraft,
    MetricTemplate,
    TemplateNotFoundError,
)
from tingle.pacts.diff import DiffResult, FileDiff, FileStatus
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

CHECKED_TYPES = {
    "file_count": MetricType(
        name="file_count",
        func=lambda _ctx: MetricResult(value=0),
        diff_func=lambda _ctx: DiffResult(net=0),
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
        strict=MagicMock(),
    )

    report = service.run(_config())

    project_files.assert_called_once_with(CWD, prune=UNREACHABLE_DIRS)
    assert [outcome.spec.name for outcome in report.outcomes] == ["files"]


def _diff_service() -> tuple[MetricsService, MagicMock, MagicMock]:
    project_files = MagicMock()
    project_files.return_value.walk.return_value = ()
    diff_source = MagicMock()
    diff_source.return_value.branch_diff.return_value.files = ()
    service = MetricsService(
        project_files=project_files,
        diff_source=diff_source,
        metric_types=METRIC_TYPES,
        strict=MagicMock(),
    )
    return service, project_files, diff_source


def test_diff_anchors_both_adapters_at_the_config_root() -> None:
    service, project_files, diff_source = _diff_service()

    service.diff(_config(), "main")

    project_files.assert_called_once_with(CWD, prune=UNREACHABLE_DIRS)
    diff_source.assert_called_once_with(CWD)
    diff_source.return_value.branch_diff.assert_called_once_with("main")


BASES = (
    pytest.param("feature", "origin/develop", "feature", id="asked"),
    pytest.param(None, "origin/develop", "origin/develop", id="configured"),
    pytest.param("", "origin/develop", "origin/develop", id="empty-asked"),
)


@pytest.mark.parametrize(("asked", "configured", "resolved"), BASES)
def test_diff_takes_the_base_asked_for_then_the_configured_one(
    asked: str | None, *, configured: str, resolved: str
) -> None:
    service, _, diff_source = _diff_service()

    service.diff(replace(_config(), diff_base=configured), asked)

    diff_source.return_value.branch_diff.assert_called_once_with(resolved)


def _at_base(store: MagicMock, templates: MagicMock | None = None) -> ConfigService:
    return ConfigService(
        store=store,
        metric_types=METRIC_TYPES,
        templates=templates or MagicMock(),
        project_files=MagicMock(),
    )


def _strict_config() -> Config:
    return validate({**RAW, "check": {"strict": True}}, METRIC_TYPES, source=SOURCE)


def test_at_base_says_when_a_strict_branch_finds_no_config() -> None:
    store = MagicMock()
    store.load_at.return_value = None

    with pytest.raises(BaseConfigError, match="the base has no config"):
        _at_base(store).at_base(_strict_config(), MagicMock())


def test_at_base_asks_nothing_of_a_branch_with_no_config_either_side() -> None:
    store = MagicMock()
    store.load_at.return_value = None

    assert _at_base(store).at_base(_config(), MagicMock()) is None


def test_at_base_says_when_the_config_cannot_be_parsed() -> None:
    store = MagicMock()
    store.load_at.side_effect = ConfigError(["bad"])

    with pytest.raises(BaseConfigError, match="the base config cannot be parsed"):
        _at_base(store).at_base(_config(), MagicMock())


def test_at_base_keeps_what_a_strict_config_names_when_it_no_longer_validates() -> None:
    store = MagicMock()
    raw = {"check": {"strict": True}, "metrics": [{"base": "pack.tools.gone"}]}
    store.load_at.return_value = (PurePath("tingle.toml"), raw)
    templates = MagicMock()
    templates.load.side_effect = TemplateNotFoundError("gone")

    with pytest.raises(BaseConfigError, match="does not validate") as caught:
        _at_base(store, templates).at_base(_config(), MagicMock())

    assert caught.value.source == PurePath("tingle.toml")
    assert caught.value.bases == ("pack.tools.gone",)


def test_at_base_names_no_bases_for_a_base_that_asked_nothing() -> None:
    store = MagicMock()
    raw = {"metrics": [{"base": "pack.tools.gone"}]}
    store.load_at.return_value = (PurePath("tingle.toml"), raw)
    templates = MagicMock()
    templates.load.side_effect = TemplateNotFoundError("gone")

    with pytest.raises(BaseConfigError, match="does not validate") as caught:
        _at_base(store, templates).at_base(_strict_config(), MagicMock())

    assert not caught.value.bases


def test_at_base_is_silent_when_only_the_branch_asks_for_strict() -> None:
    store = MagicMock()
    store.load_at.return_value = (PurePath("tingle.toml"), RAW)

    assert _at_base(store).at_base(_strict_config(), MagicMock()) is None


def test_at_base_lists_only_the_modules_inside_the_project() -> None:
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
    templates.module_file.side_effect = lambda path, _root: (
        PurePath("pack.py") if path == "in.t" else None
    )

    found = _at_base(store, templates).at_base(_config(), MagicMock())

    assert found is not None
    assert found.modules == (PurePath("pack.py"),)
    assert found.source == PurePath("tingle.toml")
    templates.module_file.assert_any_call("in.t", CWD)


def test_a_malformed_strict_on_the_base_counts_as_asked() -> None:
    store = MagicMock()
    raw = {**RAW, "check": {"strict": "yes"}}
    store.load_at.return_value = (PurePath("tingle.toml"), raw)

    with pytest.raises(BaseConfigError, match="does not validate"):
        _at_base(store).at_base(_config(), MagicMock())


def test_at_base_resolves_nothing_when_neither_side_asks_for_strict() -> None:
    store = MagicMock()
    store.load_at.return_value = (PurePath("tingle.toml"), RAW)
    templates = MagicMock()

    assert _at_base(store, templates).at_base(_config(), MagicMock()) is None
    templates.load.assert_not_called()


def _check_service(*changed: str) -> tuple[MetricsService, MagicMock, MagicMock]:
    project_files = MagicMock()
    project_files.return_value.walk.return_value = ()
    diff_source = MagicMock()
    diff_source.return_value.branch_diff.return_value.files = tuple(
        FileDiff(path=PurePath(path), status=FileStatus.MODIFIED) for path in changed
    )
    strict = MagicMock()
    strict.judge.return_value = StrictVerdict()
    service = MetricsService(
        project_files=project_files,
        diff_source=diff_source,
        metric_types=CHECKED_TYPES,
        strict=strict,
    )
    return service, strict, diff_source


def test_check_diffs_at_the_config_root() -> None:
    service, _, diff_source = _check_service("a.py")

    service.check(_config(), "main")

    diff_source.assert_called_once_with(CWD)
    diff_source.return_value.branch_diff.assert_called_once_with("main")


@pytest.mark.parametrize(("asked", "configured", "resolved"), BASES)
def test_check_takes_the_base_asked_for_then_the_configured_one(
    asked: str | None, *, configured: str, resolved: str
) -> None:
    service, _, diff_source = _check_service("a.py")

    service.check(replace(_config(), diff_base=configured), asked)

    diff_source.return_value.branch_diff.assert_called_once_with(resolved)


def test_check_has_strict_judged_through_the_source_that_diffed() -> None:
    service, strict, diff_source = _check_service("a.py")
    strict.judge.return_value = StrictVerdict(skipped="strict mode skipped: why")
    config = _config()

    report, verdict = service.check(config, "main")

    strict.judge.assert_called_once_with(
        config, read_base=diff_source.return_value.read_base, report=report
    )
    assert verdict.strict == strict.judge.return_value
