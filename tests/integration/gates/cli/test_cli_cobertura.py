from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lxml import etree
from typer.testing import CliRunner

from tingle.gates.cli.typer import app

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
pattern = '#\\s*noqa'

[[metrics]]
name = "ruff-ignores"
type = "toml_list_length"
key = "tool.ruff.lint.ignore"
"""


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "tingle.toml").write_text(CONFIG)
    (tmp_path / "pyproject.toml").write_text('[tool.ruff.lint]\nignore = ["E501"]\n')
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text("x = 1  # noqa\ny = 2\nz = 3  # noqa\n")
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.usefixtures("project")
def test_cobertura_marks_occurrence_lines_uncovered() -> None:
    result = runner.invoke(app, ["report", "--cobertura"])

    assert result.exit_code == 0
    # bytes, not str: the report carries an encoding declaration, and lxml
    # refuses to parse those from a unicode string
    root = etree.fromstring(result.stdout.encode())
    assert root.tag == "coverage"
    assert root.get("lines-valid") == "2"
    assert root.get("lines-covered") == "0"

    packages = {p.get("name"): p for p in root.iter("package")}
    assert list(packages) == ["noqa-comments"]
    lines = [
        (cls.get("filename"), line.get("number"), line.get("hits"))
        for cls in packages["noqa-comments"].iter("class")
        for line in cls.iter("line")
    ]
    assert lines == [("src/a.py", "1", "0"), ("src/a.py", "3", "0")]


@pytest.mark.usefixtures("project")
def test_cobertura_notes_excluded_metrics_on_stderr() -> None:
    result = runner.invoke(app, ["report", "--cobertura"])

    assert "note: ruff-ignores: not representable in cobertura" in result.stderr


@pytest.mark.usefixtures("project")
def test_cobertura_conflicts_with_json_and_diff() -> None:
    with_json = runner.invoke(app, ["report", "--cobertura", "--json"])
    with_diff = runner.invoke(app, ["report", "--cobertura", "--diff"])

    assert with_json.exit_code == 2
    assert with_diff.exit_code == 2
