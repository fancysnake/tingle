from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from conftest import STRICT_CONFIG
from typer.testing import CliRunner

from tingle.gates.cli.typer import CliGate
from tingle.inits.services import Services

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
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
        "strict": {"loosened": [], "alongside": [], "skipped": None},
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
    assert "No such option" in result.stderr


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


def _loosen(repo: Path) -> None:
    config = (repo / "tingle.toml").read_text()
    (repo / "tingle.toml").write_text(f"{config}ignore_lines = ['^x = ']\n")


def test_strict_fails_loosening_that_rides_with_another_change(
    strict_repo: Path,
) -> None:
    _loosen(strict_repo)
    (strict_repo / "b.py").write_text("y = 2\n")

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 1
    assert "debt: 1 to 0" in result.output
    assert "~ b.py" in result.output
    assert "debt loosened alongside 1 other changed file" in result.stderr


def test_strict_passes_loosening_on_its_own(strict_repo: Path) -> None:
    _loosen(strict_repo)

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 0


def test_strict_cannot_be_turned_off_by_the_branch_it_judges(strict_repo: Path) -> None:
    config = (strict_repo / "tingle.toml").read_text()
    (strict_repo / "tingle.toml").write_text(
        config.replace("strict = true", "strict = false")
    )
    (strict_repo / "b.py").write_text("y = 2\n")

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 1
    assert "[check] strict: turned off" in result.output


def test_strict_is_not_lost_by_pointing_at_another_config(strict_repo: Path) -> None:
    (strict_repo / "lax.toml").write_text(
        STRICT_CONFIG.replace("strict = true", "").replace("debt'", "never'")
    )
    (strict_repo / "b.py").write_text("y = 2\n")

    result = runner.invoke(app, ["check", "--config", "lax.toml"])

    assert result.exit_code == 1
    assert "debt: 1 to 0" in result.output


def test_strict_ignores_a_config_that_tightens(strict_repo: Path) -> None:
    config = (strict_repo / "tingle.toml").read_text()
    (strict_repo / "tingle.toml").write_text(
        f'{config}\n[[metrics]]\nname = "more"\n'
        'type = "regex_count"\npattern = "[z]q"\n'
    )
    (strict_repo / "b.py").write_text("z = 2\n")

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 0


def _in_pyproject(extra: str = "", version: str = "1") -> str:
    section = STRICT_CONFIG.replace("[check]", "[tool.tingle.check]").replace(
        "[[metrics]]", "[[tool.tingle.metrics]]"
    )
    return f'[project]\nversion = "{version}"\n{section}{extra}\n'


def test_strict_in_pyproject_tells_config_from_the_rest_of_the_file(
    branched: Callable[[Mapping[str, str]], Path],
) -> None:
    repo = branched({"pyproject.toml": _in_pyproject(), "a.py": "x = 1  # debt\n"})
    ignored = "ignore_lines = ['^x = ']"

    (repo / "pyproject.toml").write_text(_in_pyproject(ignored))
    alone = runner.invoke(app, ["check"])
    (repo / "pyproject.toml").write_text(_in_pyproject(ignored, version="2"))
    alongside = runner.invoke(app, ["check"])

    assert alone.exit_code == 0
    assert alongside.exit_code == 1
    assert "~ pyproject.toml" in alongside.output


def test_strict_says_so_when_the_base_has_no_config(
    branched: Callable[[Mapping[str, str]], Path],
) -> None:
    repo = branched({"a.py": "x = 1\n"})
    (repo / "tingle.toml").write_text(STRICT_CONFIG)

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 0
    assert "strict mode skipped: the base has no config" in result.output


def test_strict_has_nothing_to_measure_when_the_base_ignores_every_metric(
    branched: Callable[[Mapping[str, str]], Path],
) -> None:
    config = STRICT_CONFIG.replace("strict = true", 'strict = true\nignore = ["debt"]')
    repo = branched({"tingle.toml": config, "a.py": "x = 1\n"})
    (repo / "b.py").write_text("y = 2  # debt\n")

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 0


def test_strict_counts_a_changed_project_template_module_as_config(
    branched: Callable[[Mapping[str, str]], Path], pack: str
) -> None:
    config = f'[check]\nstrict = true\n\n[[metrics]]\nbase = "{pack}.tools.noqa"\n'
    repo = branched({"tingle.toml": config, ".gitignore": "__pycache__\n"})
    module = repo / pack / "tools.py"
    module.write_text(f"{module.read_text()}\n# narrowed\n")

    alone = runner.invoke(app, ["check"])
    (repo / "b.py").write_text("y = 2\n")
    alongside = runner.invoke(app, ["check"])

    assert alone.exit_code == 0
    assert alongside.exit_code == 1
    assert f"{pack}/tools.py: template module changed" in alongside.output
    assert "~ b.py" in alongside.output


def test_the_branch_that_turns_strict_on_is_not_held_to_it(
    branched: Callable[[Mapping[str, str]], Path],
) -> None:
    config = STRICT_CONFIG.replace("strict = true", "")
    repo = branched({"tingle.toml": config, "a.py": "x = 1  # debt\n"})
    (repo / "tingle.toml").write_text(f"{STRICT_CONFIG}ignore_lines = ['^x = ']\n")
    (repo / "b.py").write_text("y = 2\n")

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 0
