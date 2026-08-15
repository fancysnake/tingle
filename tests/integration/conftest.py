"""Fixtures shared by every integration test.

`isolated_git` lives here rather than beside the tests that build repos
because two suites need it -- the CLI gate's and the git link's -- and a
copy in each is a copy that can drift.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


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
