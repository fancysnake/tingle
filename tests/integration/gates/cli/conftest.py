"""Fixtures shared by the CLI gate's integration tests.

The workdir/repo fixtures live here rather than in the test modules so
that a test asking for `repo: Path` does not shadow the fixture function
of the same name — pytest requires the parameter to match the fixture.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

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


@pytest.fixture
def config_text() -> str:
    """Return the tingle.toml the repo fixture is built around."""
    return CONFIG


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Make an empty directory the current one, and return it."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture(autouse=True)
def isolated_git(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep git off the developer's own config and out of enclosing repos."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", "/dev/null")
    monkeypatch.setenv("GIT_AUTHOR_NAME", "tingle-tests")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "tests@tingle.invalid")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "tingle-tests")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "tests@tingle.invalid")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))


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
