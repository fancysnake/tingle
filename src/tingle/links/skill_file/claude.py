"""Claude Code adapter for a project's agent skills."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tingle.pacts.skill import SkillExistsError, SkillStore

if TYPE_CHECKING:
    from pathlib import Path

SKILLS_DIR = ".claude/skills"
SKILL_FILE = "SKILL.md"


class ClaudeSkillStore(SkillStore):
    """Project skills as Claude Code reads them: a SKILL.md per directory."""

    def create(self, root: Path, *, name: str, text: str) -> Path:
        """Write `<SKILLS_DIR>/<name>/SKILL.md`; refuse to overwrite."""
        target = root / SKILLS_DIR / name / SKILL_FILE
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            file = target.open("x", encoding="utf-8")
        except FileExistsError:
            msg = f"{target} already exists"
            raise SkillExistsError(msg) from None
        with file:
            file.write(text)
        return target
