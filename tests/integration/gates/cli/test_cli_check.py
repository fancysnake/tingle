from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from tingle.gates.cli.typer import CliGate
from tingle.inits.services import Services

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
app = CliGate(Services()).app


def _configure(repo: Path, check: str) -> None:
    """Append a [check] section to the repo fixture's config."""
    config = (repo / "tingle.toml").read_text()
    (repo / "tingle.toml").write_text(f"{config}\n{check}\n")


@pytest.mark.usefixtures("repo")
def test_worsening_branch_fails_under_the_default_sum_policy() -> None:
    result = runner.invoke(app, ["check"])

    assert result.exit_code == 1
    assert "check failed: metrics grew by a net +4" in result.stderr


@pytest.mark.usefixtures("repo")
def test_only_added_lines_are_printed(repo: Path) -> None:
    (repo / "src" / "a.py").write_text("y = 2  # noqa\nz = 3  # noqa\n")  # drops one

    result = runner.invoke(app, ["check"])

    assert "+ src/a.py:1" in result.output
    assert "+ pyproject.toml: D203" in result.output
    # the removed occurrence is real, but check never shows it
    assert not any(line.lstrip().startswith("-") for line in result.output.splitlines())
    # nor the summary table's columns
    assert "Net" not in result.output
    assert "Total" not in result.output


def test_a_clean_branch_says_so(repo: Path) -> None:
    """A passing check must say so.

    It printed nothing at all before, which in a CI log cannot be told apart
    from a step that never ran.
    """
    (repo / "src" / "new.py").unlink()
    (repo / "src" / "a.py").write_text("x = 1  # noqa\n")
    (repo / "pyproject.toml").write_text('[tool.ruff.lint]\nignore = ["E501"]\n')

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 0
    assert "🎉 no new debt" in result.output
    assert "against main" in result.output
    # and it still lists nothing: there is no debt to answer for
    assert not any(line.lstrip().startswith("+") for line in result.output.splitlines())


@pytest.mark.usefixtures("repo")
def test_a_failing_check_says_nothing_about_success() -> None:
    result = runner.invoke(app, ["check"])

    assert result.exit_code == 1
    assert "🎉" not in result.output


def test_sum_policy_lets_a_gain_offset_a_loss(repo: Path) -> None:
    """One noqa added, two removed elsewhere: net -1, so the branch lands."""
    (repo / "src" / "new.py").unlink()
    (repo / "src" / "a.py").write_text("x = 1\ny = 2\nz = 3  # noqa\n")
    (repo / "pyproject.toml").write_text('[tool.ruff.lint]\nignore = ["E501"]\n')

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 0


def _trade(repo: Path) -> None:
    """One noqa taken on, one ruff ignore paid off: net zero overall."""
    (repo / "src" / "new.py").unlink()
    (repo / "src" / "a.py").write_text("x = 1  # noqa\ny = 2  # noqa\n")
    (repo / "pyproject.toml").write_text("[tool.ruff.lint]\nignore = []\n")


def test_sum_policy_allows_an_even_trade(repo: Path) -> None:
    _trade(repo)

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 0


def test_any_policy_rejects_the_trade_sum_allows(repo: Path) -> None:
    _trade(repo)
    _configure(repo, '[check]\npolicy = "any"')

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 1
    assert "noqa-comments grew (policy: any)" in result.stderr


@pytest.mark.usefixtures("repo")
def test_policy_flag_overrides_the_config(repo: Path) -> None:
    _configure(repo, '[check]\npolicy = "sum"')

    result = runner.invoke(app, ["check", "--policy", "any"])

    assert result.exit_code == 1
    assert "(policy: any)" in result.stderr


@pytest.mark.usefixtures("repo")
def test_ignored_metric_neither_fails_nor_prints(repo: Path) -> None:
    _configure(repo, '[check]\npolicy = "any"\nignore = ["noqa-comments"]')

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 1  # ruff-ignores still grew
    assert "noqa-comments" not in result.output
    assert "src/a.py" not in result.output
    assert "ruff-ignores" in result.output


def test_ignoring_every_grown_metric_passes(repo: Path) -> None:
    _configure(repo, '[check]\nignore = ["noqa-comments", "ruff-ignores"]')

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 0
    # nothing to answer for, and the ignored metrics are not even counted
    assert "🎉 no new debt" in result.output
    assert "noqa-comments" not in result.output


@pytest.mark.usefixtures("repo")
def test_metric_filter_narrows_the_verdict() -> None:
    result = runner.invoke(app, ["check", "--metric", "ruff-ignores"])

    assert result.exit_code == 1
    assert "ruff-ignores" in result.output
    assert "noqa-comments" not in result.output


@pytest.mark.usefixtures("repo")
def test_unknown_policy_exits_2() -> None:
    result = runner.invoke(app, ["check", "--policy", "every"])

    assert result.exit_code == 2
    assert 'unknown --policy "every"' in result.stderr


@pytest.mark.usefixtures("repo")
def test_unknown_ignored_metric_is_a_config_error(repo: Path) -> None:
    _configure(repo, '[check]\nignore = ["nope"]')

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 2
    assert 'unknown metric "nope" in ignore' in result.stderr


@pytest.mark.usefixtures("repo")
def test_missing_base_exits_2() -> None:
    result = runner.invoke(app, ["check", "--base", "nope"])

    assert result.exit_code == 2
    assert 'base ref "nope" not found' in result.stderr


def test_check_outside_repo_exits_2(workdir: Path, config_text: str) -> None:
    (workdir / "tingle.toml").write_text(config_text)

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 2
    assert "diff error" in result.stderr
