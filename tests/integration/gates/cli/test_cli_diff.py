from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from tingle.gates.cli.typer import CliGate
from tingle.inits.services import Services
from tingle.mills.metrics.registry import METRIC_TYPES
from tingle.pacts.metrics import MetricType

if TYPE_CHECKING:
    from pathlib import Path

    from tingle.pacts.diff import DiffMetricContext, DiffResult

runner = CliRunner()
app = CliGate(Services()).app


@pytest.mark.usefixtures("repo")
def test_stat_diff_table() -> None:
    result = runner.invoke(app, ["stat", "--diff"])

    assert result.exit_code == 0
    assert "noqa-comments" in result.output
    assert "+3" in result.output
    assert "ruff-ignores" in result.output
    assert "+1" in result.output


@pytest.mark.usefixtures("repo")
def test_stat_diff_json_is_values_only() -> None:
    result = runner.invoke(app, ["stat", "--json", "--diff"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["base"] == "main"
    assert len(payload["merge_base"]) == 40
    metrics = {entry["name"]: entry for entry in payload["metrics"]}

    noqa = metrics["noqa-comments"]
    assert noqa["added"] == 3
    assert noqa["net"] == 3
    assert noqa["total"] == 4
    assert "added_occurrences" not in noqa
    assert "removed_occurrences" not in noqa
    assert "details" not in noqa

    assert metrics["ruff-ignores"]["net"] == 1


@pytest.mark.usefixtures("repo")
def test_report_diff_json_includes_occurrences() -> None:
    result = runner.invoke(app, ["report", "--json", "--diff"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    metrics = {entry["name"]: entry for entry in payload["metrics"]}

    noqa = metrics["noqa-comments"]
    assert noqa["added"] == 3
    assert noqa["total"] == 4
    assert {"file": "src/a.py", "line": 2, "note": None} in noqa["added_occurrences"]
    assert {"file": "src/new.py", "line": 1, "note": None} in noqa["added_occurrences"]

    ignores = metrics["ruff-ignores"]
    assert ignores["net"] == 1
    assert ignores["added_occurrences"] == [
        {"file": "pyproject.toml", "line": None, "note": "D203"}
    ]


@pytest.mark.usefixtures("repo")
def test_report_diff_lists_signed_occurrences(repo: Path) -> None:
    (repo / "src" / "a.py").write_text("x = 1\ny = 2  # noqa\nz = 3  # noqa\n")

    result = runner.invoke(app, ["report", "--diff"])

    assert result.exit_code == 0
    assert "+ src/a.py:2" in result.output
    assert "- src/a.py:1" in result.output
    assert "+ pyproject.toml: D203" in result.output


@pytest.mark.usefixtures("repo")
def test_base_flag_implies_diff() -> None:
    result = runner.invoke(app, ["stat", "--base", "main"])

    assert result.exit_code == 0
    assert "Net" in result.output


@pytest.mark.usefixtures("repo")
def test_diff_metric_filter() -> None:
    result = runner.invoke(
        app, ["stat", "--json", "--diff", "--metric", "ruff-ignores"]
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [entry["name"] for entry in payload["metrics"]] == ["ruff-ignores"]


@pytest.mark.usefixtures("repo")
def test_missing_base_exits_2() -> None:
    result = runner.invoke(app, ["stat", "--diff", "--base", "nope"])

    assert result.exit_code == 2
    assert 'base ref "nope" not found' in result.stderr


@pytest.mark.usefixtures("repo")
def test_base_from_config(repo: Path) -> None:
    config = (repo / "tingle.toml").read_text()
    (repo / "tingle.toml").write_text(config + '\n[diff]\nbase = "nope"\n')

    result = runner.invoke(app, ["stat", "--diff"])

    assert result.exit_code == 2
    assert 'base ref "nope" not found' in result.stderr


@pytest.mark.usefixtures("repo")
def test_raising_diff_metric_exits_1_but_others_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(_: DiffMetricContext) -> DiffResult:
        msg = "boom"
        raise RuntimeError(msg)

    original = METRIC_TYPES["toml_list_length"]
    monkeypatch.setitem(
        METRIC_TYPES,
        "toml_list_length",
        MetricType(
            name="toml_list_length",
            func=original.func,
            params=original.params,
            diff_func=boom,
        ),
    )

    result = runner.invoke(app, ["stat", "--json", "--diff"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    metrics = {entry["name"]: entry for entry in payload["metrics"]}
    assert metrics["ruff-ignores"]["error"] == "RuntimeError: boom"
    assert metrics["noqa-comments"]["net"] == 3
    assert "error: ruff-ignores: RuntimeError: boom" in result.stderr


def test_diff_outside_repo_exits_2(workdir: Path, config_text: str) -> None:
    (workdir / "tingle.toml").write_text(config_text)

    result = runner.invoke(app, ["stat", "--diff"])

    assert result.exit_code == 2
    assert "diff error" in result.stderr


def test_diff_command_is_gone() -> None:
    result = runner.invoke(app, ["diff"])

    assert result.exit_code != 0
