from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lxml import etree
from typer.testing import CliRunner

from tingle.gates.cli.typer import CliGate
from tingle.inits.services import Services

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
app = CliGate(Services()).app


@pytest.fixture
def project(workdir: Path, config_text: str) -> Path:
    (workdir / "tingle.toml").write_text(config_text)
    (workdir / "pyproject.toml").write_text('[tool.ruff.lint]\nignore = ["E501"]\n')
    src = workdir / "src"
    src.mkdir()
    (src / "a.py").write_text("x = 1  # noqa\ny = 2\nz = 3  # noqa\n")
    return workdir


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
    assert list(packages) == ["lint-escapes"]
    lines = [
        (cls.get("filename"), line.get("number"), line.get("hits"))
        for cls in packages["lint-escapes"].iter("class")
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
