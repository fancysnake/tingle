from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from tingle.gates.cli.typer import CliGate
from tingle.inits.services import Services

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
app = CliGate(Services()).app

SKILL = ".claude/skills/tingle-fix/SKILL.md"

THREE_METRICS = """
[[metrics]]
base = "tingle.builtins.ruff.noqa_comment"

[[metrics]]
name = "todo-comments"
type = "regex_count"
pattern = '#\\s*TODO'
description = "Work left for later."

[[metrics]]
name = "python-files"
type = "file_count"
"""


def test_skill_writes_a_placeholder_for_every_configured_metric(workdir: Path) -> None:
    (workdir / "tingle.toml").write_text(THREE_METRICS)

    result = runner.invoke(app, ["skill"])

    assert result.exit_code == 0
    assert result.stdout == f"Created {workdir / SKILL}\n"
    text = (workdir / SKILL).read_text(encoding="utf-8")
    assert text.startswith("---\nname: tingle-fix\n")
    for name in ("noqa-comment", "todo-comments", "python-files"):
        assert f"\n### {name}\n" in text
    assert text.count("\n_No guidance yet._\n") == len(
        ("noqa-comment", "todo-comments", "python-files")
    )
    assert "\n### todo-comments\n\nWork left for later.\n\n_No guidance yet._\n" in text


def test_skill_refuses_to_overwrite_the_one_in_the_project(workdir: Path) -> None:
    (workdir / "tingle.toml").write_text(THREE_METRICS)
    existing = workdir / SKILL
    existing.parent.mkdir(parents=True)
    existing.write_text("the project's text")

    result = runner.invoke(app, ["skill"])

    assert result.exit_code == 2
    assert result.stderr == f"skill error: {existing} already exists\n"
    assert existing.read_text() == "the project's text"


def test_skill_lands_beside_the_config_it_was_pointed_at(workdir: Path) -> None:
    project = workdir / "project"
    project.mkdir()
    (project / "tingle.toml").write_text(THREE_METRICS)

    result = runner.invoke(app, ["skill", "--config", "project/tingle.toml"])

    assert result.exit_code == 0
    assert (project / SKILL).is_file()
    assert not (workdir / ".claude").exists()


def test_skill_without_a_config_is_a_config_error(workdir: Path) -> None:
    result = runner.invoke(app, ["skill"])

    assert result.exit_code == 2
    assert "config error:" in result.stderr
    assert not (workdir / ".claude").exists()
