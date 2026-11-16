from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tingle.links.skill_file.claude import ClaudeSkillStore
from tingle.pacts.skill import SkillExistsError

if TYPE_CHECKING:
    from pathlib import Path

create = ClaudeSkillStore().create


def test_create_writes_the_skill_where_claude_code_reads_project_skills(
    tmp_path: Path,
) -> None:
    written = create(tmp_path, name="tingle-fix", text="# text\n")

    assert written == tmp_path / ".claude" / "skills" / "tingle-fix" / "SKILL.md"
    assert written.read_text(encoding="utf-8") == "# text\n"


def test_create_leaves_the_skills_already_in_the_project(tmp_path: Path) -> None:
    other = tmp_path / ".claude" / "skills" / "other" / "SKILL.md"
    other.parent.mkdir(parents=True)
    other.write_text("theirs")

    create(tmp_path, name="tingle-fix", text="# text\n")

    assert other.read_text() == "theirs"


def test_create_refuses_to_overwrite(tmp_path: Path) -> None:
    written = create(tmp_path, name="tingle-fix", text="the project's text")

    with pytest.raises(SkillExistsError, match=r"SKILL\.md already exists"):
        create(tmp_path, name="tingle-fix", text="# text\n")

    assert written.read_text() == "the project's text"
