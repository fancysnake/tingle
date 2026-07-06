from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from tingle import __version__
from tingle.gates.cli.typer import app
from tingle.inits.wiring import METRIC_TYPES
from tingle.pacts.metrics import MetricContext, MetricResult, MetricType

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()

CONFIG = """
[ranges.python]
include = ["src/**/*.py"]
default = true

[[metrics]]
name = "noqa-comments"
type = "regex_count"
range = "python"
pattern = '#\\s*noqa'

[[metrics]]
name = "python-files"
type = "file_count"
"""


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "tingle.toml").write_text(CONFIG)
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text("x = 1  # noqa\ny = 2  # noqa\n")
    (src / "b.py").write_text("z = 3  # noqa\n")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


@pytest.mark.usefixtures("project")
def test_bare_invocation_prints_summary_when_not_a_tty() -> None:
    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "noqa-comments" in result.output
    assert "3" in result.output
    assert "python-files" in result.output


@pytest.mark.usefixtures("project")
def test_stat_table() -> None:
    result = runner.invoke(app, ["stat"])

    assert result.exit_code == 0
    assert "noqa-comments" in result.output
    assert "3" in result.output


@pytest.mark.usefixtures("project")
def test_stat_json_includes_occurrences() -> None:
    result = runner.invoke(app, ["stat", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["config"].endswith("tingle.toml")
    metrics = {entry["name"]: entry for entry in payload["metrics"]}
    noqa = metrics["noqa-comments"]
    assert noqa["value"] == 3
    assert noqa["details"] == {"src/a.py": 2, "src/b.py": 1}
    assert noqa["occurrences"] == [
        {"file": "src/a.py", "line": 1, "note": None},
        {"file": "src/a.py", "line": 2, "note": None},
        {"file": "src/b.py", "line": 1, "note": None},
    ]
    assert metrics["python-files"]["value"] == 2


@pytest.mark.usefixtures("project")
def test_report_lists_occurrences() -> None:
    result = runner.invoke(app, ["report"])

    assert result.exit_code == 0
    assert "noqa-comments (regex_count): 3" in result.output
    assert "src/a.py:1" in result.output
    assert "src/a.py:2" in result.output
    assert "src/b.py:1" in result.output
    assert "python-files (file_count): 2" in result.output


@pytest.mark.usefixtures("project")
def test_report_json_matches_stat_json() -> None:
    stat = runner.invoke(app, ["stat", "--json"])
    report = runner.invoke(app, ["report", "--json"])

    assert json.loads(stat.stdout) == json.loads(report.stdout)


@pytest.mark.usefixtures("project")
def test_metric_filter() -> None:
    result = runner.invoke(app, ["stat", "--json", "--metric", "python-files"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [entry["name"] for entry in payload["metrics"]] == ["python-files"]


@pytest.mark.usefixtures("project")
def test_unknown_metric_filter_exits_2() -> None:
    result = runner.invoke(app, ["stat", "--metric", "nope"])

    assert result.exit_code == 2
    assert 'unknown metric "nope"' in result.stderr


def test_missing_config_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["stat"])

    assert result.exit_code == 2
    assert "config error" in result.stderr


def test_invalid_config_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "tingle.toml").write_text('[[metrics]]\nname = "x"\ntype = "nope"\n')
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["stat"])

    assert result.exit_code == 2
    assert "unknown type 'nope'" in result.stderr


@pytest.mark.usefixtures("project")
def test_raising_metric_exits_1_but_others_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(_: MetricContext) -> MetricResult:
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setitem(
        METRIC_TYPES, "file_count", MetricType(name="file_count", func=boom)
    )

    result = runner.invoke(app, ["stat", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    metrics = {entry["name"]: entry for entry in payload["metrics"]}
    assert metrics["python-files"]["error"] == "RuntimeError: boom"
    assert metrics["python-files"]["value"] is None
    assert metrics["noqa-comments"]["value"] == 3
    assert "error: python-files: RuntimeError: boom" in result.stderr


@pytest.mark.usefixtures("project")
def test_run_command_is_gone() -> None:
    result = runner.invoke(app, ["run"])

    assert result.exit_code != 0


@pytest.mark.usefixtures("project")
def test_list_shows_configured_metrics() -> None:
    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "noqa-comments" in result.output
    assert "regex_count" in result.output


def test_list_types_works_without_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["list", "--types"])

    assert result.exit_code == 0
    for name in METRIC_TYPES:
        assert name in result.output
