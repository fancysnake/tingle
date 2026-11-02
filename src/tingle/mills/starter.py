"""Choosing what `tingle init` writes from what the project configures."""

from __future__ import annotations

import configparser
import re
import tomllib
from pathlib import PurePath
from typing import TYPE_CHECKING

from tingle.mills.text import decode_text
from tingle.specs.starter import INI_FILES, PYPROJECT_FILE, STARTER_TOOLS

if TYPE_CHECKING:
    from tingle.pacts.metrics import ProjectFiles


def starter_bases(project: ProjectFiles) -> tuple[str, ...]:
    """Return the template bases of every recognised tool the project configures."""
    named = _configured(project)
    return tuple(
        dict.fromkeys(
            base
            for tool in STARTER_TOOLS
            if tool.name in named
            or any(project.exists(PurePath(file)) for file in tool.files)
            for base in tool.bases
        )
    )


def _configured(project: ProjectFiles) -> set[str]:
    """Name every tool the shared config files hold a section for.

    A file that does not parse names nothing, not even the sections read
    before the error: this is a guess at a starter, and the tool the file
    belongs to will report it.
    """
    names = set(_pyproject_tools(project))
    for file in INI_FILES:
        names.update(_ini_tools(project, file))
    return names


def _pyproject_tools(project: ProjectFiles) -> list[str]:
    if (text := decode_text(project.read(PurePath(PYPROJECT_FILE)))) is None:
        return []
    try:
        tools = tomllib.loads(text).get("tool")
    except tomllib.TOMLDecodeError:
        return []
    return list(tools) if isinstance(tools, dict) else []


def _ini_tools(project: ProjectFiles, file: str) -> list[str]:
    if (text := decode_text(project.read(PurePath(file)))) is None:
        return []
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(text)
    except configparser.Error:
        return []
    return [_tool_name(section) for section in parser.sections()]


def _tool_name(section: str) -> str:
    """`[tool:pytest]`, `[coverage:run]` and `[pylint.main]` each name their tool."""
    return re.split(r"[:.]", section.removeprefix("tool:"), maxsplit=1)[0]
