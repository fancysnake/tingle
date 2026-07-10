from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from tingle.gates.cli.typer import app
from tingle.inits.wiring import METRIC_TYPES
from tingle.pacts.metrics import MetricType

if TYPE_CHECKING:
    from pathlib import Path

    from tingle.pacts.diff import DiffMetricContext, DiffResult

runner = CliRunner()

CONFIG = """
[ranges.python]
include = ["src/**/*.py"]
default = true

[[metrics]]
name = "noqa-comments"
type = "regex_count"
pattern = '#\\s*noqa'

[[metrics]]
name = "ruff-ignores"
type = "toml_list_length"
key = "tool.ruff.lint.ignore"
"""

BASE_PYPROJECT = '[tool.ruff.lint]\nignore = ["E501"]\n'
BRANCH_PYPROJECT = '[tool.ruff.lint]\nignore = ["E501", "D203"]\n'


@pytest.fixture(autouse=True)
def isolated_git(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", "/dev/null")
    monkeypatch.setenv("GIT_AUTHOR_NAME", "tingle-tests")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "tests@tingle.invalid")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "tingle-tests")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "tests@tingle.invalid")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Repo on branch `feature`: +2 committed noqa, +1 untracked, +1 ignore."""
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    _git(repo, "init", "-b", "main")
    (repo / "tingle.toml").write_text(CONFIG)
    (repo / "pyproject.toml").write_text(BASE_PYPROJECT)
    (src / "a.py").write_text("x = 1  # noqa\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "base")
    _git(repo, "checkout", "-b", "feature")
    (src / "a.py").write_text("x = 1  # noqa\ny = 2  # noqa\nz = 3  # noqa\n")
    (repo / "pyproject.toml").write_text(BRANCH_PYPROJECT)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "feature work")
    (src / "new.py").write_text("w = 4  # noqa\n")  # untracked
    monkeypatch.chdir(repo)
    return repo


@pytest.mark.usefixtures("repo")
def test_stat_diff_table() -> None:
    result = runner.invoke(app, ["stat", "--diff"])

    assert result.exit_code == 0
    assert "noqa-comments" in result.output
    assert "+3" in result.output
    assert "ruff-ignores" in result.output
    assert "+1" in result.output


@pytest.mark.usefixtures("repo")
def test_stat_diff_json_includes_occurrences() -> None:
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
            required_params=original.required_params,
            optional_params=original.optional_params,
            primary_param=original.primary_param,
            validate_params=original.validate_params,
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


def test_diff_outside_repo_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "tingle.toml").write_text(CONFIG)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["stat", "--diff"])

    assert result.exit_code == 2
    assert "diff error" in result.stderr


def test_diff_command_is_gone() -> None:
    result = runner.invoke(app, ["diff"])

    assert result.exit_code != 0
