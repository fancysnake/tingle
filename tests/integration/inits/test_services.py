from __future__ import annotations

from typing import TYPE_CHECKING

from tingle.inits.wiring import diff_source, project_files
from tingle.links.fs.local import LocalProjectFiles
from tingle.links.git.cli import GitCli

if TYPE_CHECKING:
    from pathlib import Path


def test_project_files_returns_local_adapter(tmp_path: Path) -> None:
    assert isinstance(project_files(tmp_path), LocalProjectFiles)


def test_diff_source_returns_git_adapter(tmp_path: Path) -> None:
    assert isinstance(diff_source(tmp_path), GitCli)
