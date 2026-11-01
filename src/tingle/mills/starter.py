"""Choosing what `tingle init` writes from what the project configures."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tingle.specs.starter import STARTER_TOOLS

if TYPE_CHECKING:
    from tingle.pacts.config import ToolConfigs


def starter_bases(found: ToolConfigs) -> tuple[str, ...]:
    """Return the template bases of every recognised tool the project configures."""
    return tuple(
        base
        for tool in STARTER_TOOLS
        if tool.files & found.files or tool.sections & found.sections
        for base in tool.bases
    )
