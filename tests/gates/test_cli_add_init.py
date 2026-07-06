import json
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from tingle.gates.cli.typer import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_add_creates_config_and_round_trips(workdir: Path) -> None:
    (workdir / "src").mkdir()
    (workdir / "src" / "a.py").write_text("x = 1  # noqa\n")

    added = runner.invoke(app, ["add", "regex_count", r"#\s*noqa"])

    assert added.exit_code == 0
    assert 'Added metric "regex_count-s-noqa"' in added.output
    assert (workdir / "tingle.toml").is_file()

    ran = runner.invoke(app, ["run", "--format", "json"])

    assert ran.exit_code == 0
    payload = json.loads(ran.stdout)
    assert payload["metrics"][0]["name"] == "regex_count-s-noqa"
    assert payload["metrics"][0]["value"] == 1


def test_add_appends_preserving_comments(workdir: Path) -> None:
    original = (
        "# hand-written config\n"
        "[ranges.python]\n"
        'include = ["src/**/*.py"]\n'
        "default = true\n"
    )
    (workdir / "tingle.toml").write_text(original)

    result = runner.invoke(
        app,
        ["add", "regex_count", "TODO", "--name", "todos", "--range", "python"],
    )

    assert result.exit_code == 0
    text = (workdir / "tingle.toml").read_text()
    assert "# hand-written config" in text
    assert 'name = "todos"' in text
    assert 'range = "python"' in text


def test_add_multiple_ranges(workdir: Path) -> None:
    (workdir / "tingle.toml").write_text(
        '[ranges.a]\ninclude = ["**/*.a"]\n\n[ranges.b]\ninclude = ["**/*.b"]\n'
    )

    result = runner.invoke(
        app,
        ["add", "regex_count", "x", "--range", "a", "--range", "b"],
    )

    assert result.exit_code == 0
    assert 'ranges = ["a", "b"]' in (workdir / "tingle.toml").read_text()


def test_add_with_params_only(workdir: Path) -> None:
    result = runner.invoke(
        app,
        [
            "add",
            "ini_list_length",
            "--name",
            "pylint-disables",
            "--param",
            "file=.pylintrc",
            "--param",
            "section=MESSAGES CONTROL",
            "--param",
            "option=disable",
        ],
    )

    assert result.exit_code == 0
    text = (workdir / "tingle.toml").read_text()
    assert 'section = "MESSAGES CONTROL"' in text


def test_add_invalid_pattern_writes_nothing(workdir: Path) -> None:
    result = runner.invoke(app, ["add", "regex_count", "("])

    assert result.exit_code == 2
    assert "invalid pattern" in result.stderr
    assert not (workdir / "tingle.toml").exists()


def test_add_unknown_range_writes_nothing(workdir: Path) -> None:
    result = runner.invoke(app, ["add", "regex_count", "x", "--range", "nope"])

    assert result.exit_code == 2
    assert not (workdir / "tingle.toml").exists()


def test_add_bad_param_format(workdir: Path) -> None:
    result = runner.invoke(app, ["add", "file_count", "--param", "oops"])

    assert result.exit_code == 2
    assert 'invalid --param "oops"' in result.stderr
    assert not (workdir / "tingle.toml").exists()


def test_add_auto_name_deduplicates(workdir: Path) -> None:
    first = runner.invoke(app, ["add", "file_count"])
    second = runner.invoke(app, ["add", "file_count"])

    assert first.exit_code == 0
    assert second.exit_code == 0
    text = (workdir / "tingle.toml").read_text()
    assert 'name = "file_count"' in text
    assert 'name = "file_count-2"' in text


def test_add_targets_pyproject_with_tool_tingle(workdir: Path) -> None:
    (workdir / "pyproject.toml").write_text(
        '[project]\nname = "demo"\n\n[tool.tingle]\n'
    )

    result = runner.invoke(app, ["add", "file_count"])

    assert result.exit_code == 0
    assert "[[tool.tingle.metrics]]" in (workdir / "pyproject.toml").read_text()
    assert not (workdir / "tingle.toml").exists()


def test_init_creates_starter(workdir: Path) -> None:
    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    assert "Created" in result.output
    assert "[ranges.python]" in (workdir / "tingle.toml").read_text()

    ran = runner.invoke(app, ["run", "--format", "json"])
    assert ran.exit_code == 0


def test_init_refuses_overwrite(workdir: Path) -> None:
    (workdir / "tingle.toml").write_text("")

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 2
    assert "already exists" in result.stderr
