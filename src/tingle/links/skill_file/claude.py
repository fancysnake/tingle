"""Claude Code adapter for a project's agent skills."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tingle.pacts.skill import SkillExistsError, SkillStore

if TYPE_CHECKING:
    from pathlib import Path

SKILL_FILE = "SKILL.md"


@dataclass(frozen=True)
class ClaudeSkillStore(SkillStore):
    """Project skills as Claude Code reads them: a SKILL.md per directory."""

    skills_dir: str = ".claude/skills"

    def create(self, root: Path, *, name: str, text: str) -> Path:
        """Write `<skills_dir>/<name>/SKILL.md`; refuse to overwrite."""
        target = root / self.skills_dir / name / SKILL_FILE
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            file = target.open("x", encoding="utf-8")
        except FileExistsError:
            msg = f"{target} already exists"
            raise SkillExistsError(msg) from None
        with file:
            file.write(text)
        return target
