from __future__ import annotations

import json
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
    _clean(repo)

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 0
    assert "🎉 no new debt" in result.output
    assert "against main" in result.output
    # and it still lists nothing: there is no debt to answer for
    assert not any(line.lstrip().startswith("+") for line in result.output.splitlines())


@pytest.mark.usefixtures("repo")
def test_json_carries_the_diff_and_the_verdict() -> None:
    result = runner.invoke(app, ["check", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["check"] == {
        "policy": "sum",
        "failed": True,
        "net_total": 4,
        "judged": 2,
        "worsened": ["lint-escapes", "ruff-ignores"],
    }
    escapes = next(m for m in payload["metrics"] if m["name"] == "lint-escapes")
    assert {"file": "src/new.py", "line": 1, "note": None} in escapes[
        "added_occurrences"
    ]
    assert "check failed" in result.stderr


def _clean(repo: Path) -> None:
    """Put the branch back to the base's debt."""
    (repo / "src" / "new.py").unlink()
    (repo / "src" / "a.py").write_text("x = 1  # noqa\n")
    (repo / "pyproject.toml").write_text('[tool.ruff.lint]\nignore = ["E501"]\n')


def test_a_passing_json_check_prints_only_json(repo: Path) -> None:
    _clean(repo)

    result = runner.invoke(app, ["check", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["check"]["failed"] is False


@pytest.mark.usefixtures("repo")
def test_github_annotates_each_addition() -> None:
    result = runner.invoke(app, ["check", "--github"])

    assert result.exit_code == 1
    commands = result.stdout.splitlines()
    assert (
        "::error file=src/a.py,line=2,title=tingle%3A lint-escapes::lint-escapes +1"
        in commands
    )
    assert (
        "::error file=pyproject.toml,title=tingle%3A ruff-ignores"
        "::ruff-ignores +1: D203" in commands
    )
    assert all(command.startswith("::error ") for command in commands)


def test_github_paths_follow_the_config_into_a_subdirectory(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(repo.parent)

    result = runner.invoke(
        app, ["check", "--github", "--config", str(repo / "tingle.toml")]
    )

    assert f"file={repo.name}/src/a.py,line=2" in result.stdout


def test_github_warns_when_the_policy_lets_the_branch_pass(repo: Path) -> None:
    _trade(repo)

    result = runner.invoke(app, ["check", "--github"])

    assert result.exit_code == 0
    assert result.stdout.startswith("::warning file=src/a.py,line=2,")


@pytest.mark.usefixtures("repo")
def test_json_and_github_are_a_usage_error() -> None:
    result = runner.invoke(app, ["check", "--json", "--github"])

    assert result.exit_code == 2
    assert "usage error" in result.stderr


def test_markdown_writes_the_comment_body(repo: Path) -> None:
    body = repo.parent / "comment.md"

    result = runner.invoke(app, ["check", "--markdown", str(body)])

    assert result.exit_code == 1
    markdown = body.read_text()
    assert "❌ check failed: metrics grew by a net +4 (policy: sum)" in markdown
    assert "| lint-escapes | +3 | 0 | +3 | 4 |" in markdown
    assert "<summary>Added (4)</summary>" in markdown
    assert "- `ruff-ignores` `pyproject.toml: D203`" in markdown
    # the listing still goes to stdout
    assert "+ src/a.py:2" in result.stdout


def test_markdown_says_a_clean_branch_changed_nothing(repo: Path) -> None:
    _clean(repo)
    body = repo.parent / "comment.md"

    result = runner.invoke(app, ["check", "--markdown", str(body)])

    assert result.exit_code == 0
    markdown = body.read_text()
    assert "🎉 no new debt: 2 metrics against `main`" in markdown
    assert "No metric changed." in markdown
    assert "Added" not in markdown


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
    assert "lint-escapes grew (policy: any)" in result.stderr


@pytest.mark.usefixtures("repo")
@pytest.mark.parametrize(
    "option", (("--policy", "any"), ("--metric", "ruff-ignores"), ("--group", "x"))
)
def test_the_command_line_cannot_narrow_the_gate(option: tuple[str, ...]) -> None:
    """Only the config decides what is judged and how, where a review sees it."""
    result = runner.invoke(app, ["check", *option])

    assert result.exit_code == 2
    assert "No such option" in result.output + result.stderr


@pytest.mark.usefixtures("repo")
def test_ignored_metric_neither_fails_nor_prints(repo: Path) -> None:
    _configure(repo, '[check]\npolicy = "any"\nignore = ["lint-escapes"]')

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 1  # ruff-ignores still grew
    assert "lint-escapes" not in result.output
    assert "src/a.py" not in result.output
    assert "ruff-ignores" in result.output


def test_ignoring_every_grown_metric_passes(repo: Path) -> None:
    _configure(repo, '[check]\nignore = ["lint-escapes", "ruff-ignores"]')

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 0
    # nothing to answer for, and the ignored metrics are not even counted
    assert "🎉 no new debt" in result.output
    assert "lint-escapes" not in result.output


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
