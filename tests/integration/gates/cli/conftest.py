"""Fixtures shared by the CLI gate's integration tests.

The workdir/repo fixtures live here rather than in the test modules so
that a test asking for `repo: Path` does not shadow the fixture function
of the same name — pytest requires the parameter to match the fixture.
"""

from __future__ import annotations

import subprocess
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from tingle.gates.cli import typer as typer_gate
from tingle.gates.cli.textual import MetricsApp

if TYPE_CHECKING:
    from pathlib import Path

CONFIG = """
[ranges.python]
include = ["src/**/*.py"]
default = true

[[metrics]]
name = "lint-escapes"
type = "regex_count"
pattern = '#\\s*noqa'

[[metrics]]
name = "ruff-ignores"
type = "toml_list_length"
key = "tool.ruff.lint.ignore"
"""

#: Like CONFIG, but counting files instead of reading pyproject.toml -- what
#: the plain `report` tests measure, since they build no pyproject.
COUNTING_CONFIG = """
[ranges.python]
include = ["src/**/*.py"]
default = true

[[metrics]]
name = "lint-escapes"
type = "regex_count"
range = "python"
pattern = '#\\s*noqa'

[[metrics]]
name = "python-files"
type = "file_count"
"""

BASE_PYPROJECT = '[tool.ruff.lint]\nignore = ["E501"]\n'
BRANCH_PYPROJECT = '[tool.ruff.lint]\nignore = ["E501", "D203"]\n'


@pytest.fixture
def config_text() -> str:
    """Return the tingle.toml the repo fixture is built around."""
    return CONFIG


@pytest.fixture
def counting_config_text() -> str:
    """Return the tingle.toml the plain report tests are built around."""
    return COUNTING_CONFIG


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Make an empty directory the current one, and return it."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Repo on branch `feature`: +2 committed noqa, +1 untracked, +1 ignore."""
    root = tmp_path / "repo"
    src = root / "src"
    src.mkdir(parents=True)
    _git(root, "init", "-b", "main")
    (root / "tingle.toml").write_text(CONFIG)
    (root / "pyproject.toml").write_text(BASE_PYPROJECT)
    (src / "a.py").write_text("x = 1  # noqa\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "base")
    _git(root, "checkout", "-b", "feature")
    (src / "a.py").write_text("x = 1  # noqa\ny = 2  # noqa\nz = 3  # noqa\n")
    (root / "pyproject.toml").write_text(BRANCH_PYPROJECT)
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "feature work")
    (src / "new.py").write_text("w = 4  # noqa\n")  # untracked
    monkeypatch.chdir(root)
    return root


@pytest.fixture
def interactive(monkeypatch: pytest.MonkeyPatch) -> list[MetricsApp]:
    """Make stdout look like a terminal, and catch the app the gate builds.

    The app is real and so is the service graph behind it; only `run` is
    replaced, since a launched TUI would sit waiting for a keystroke.
    """
    built: list[MetricsApp] = []

    def record(self: MetricsApp) -> None:
        built.append(self)

    monkeypatch.setattr(
        typer_gate, "sys", SimpleNamespace(stdout=SimpleNamespace(isatty=lambda: True))
    )
    monkeypatch.setattr(MetricsApp, "run", record)
    return built
