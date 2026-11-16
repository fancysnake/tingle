"""Contracts for the agent skill `tingle skill` writes into a project."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pathlib import Path


class SkillExistsError(Exception):
    """A skill of that name is already in the project, and may hold its text."""


class SkillStore(Protocol):
    """Keeps a project's agent skills where its agent looks for them."""

    @abstractmethod
    def create(self, root: Path, *, name: str, text: str) -> Path:
        """Write a new skill under `root`; return the file written.

        Raises SkillExistsError if the project already has that skill.
        """
