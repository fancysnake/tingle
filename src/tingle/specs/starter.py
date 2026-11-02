"""Which tools `tingle init` recognises, and what it starts each one on."""

from __future__ import annotations

from dataclasses import dataclass

from tingle.pacts.config import BUILTIN_TEMPLATE_PACKAGE

#: Where tools other than tingle keep their sections: `[tool.X]` tables in
#: the first, INI sections in the rest.
PYPROJECT_FILE = "pyproject.toml"
INI_FILES = ("setup.cfg", "tox.ini")


@dataclass(frozen=True)
class StarterTool:
    """A tool, the configuration that gives it away, and its starter metrics.

    Its own file or a section under its name is enough, and nothing else
    counts: a tool someone installed but never configured leaves no markers
    worth a metric. The bases are the inline comments only, since those
    count the same wherever the tool keeps its own config.
    """

    name: str
    files: frozenset[str]
    bases: tuple[str, ...]


def _bases(*paths: str) -> tuple[str, ...]:
    return tuple(f"{BUILTIN_TEMPLATE_PACKAGE}.{path}" for path in paths)


#: In the order the starter lists their metrics.
STARTER_TOOLS = (
    StarterTool(
        name="ruff",
        files=frozenset({"ruff.toml", ".ruff.toml"}),
        bases=_bases("ruff.noqa_comment"),
    ),
    StarterTool(
        name="black", files=frozenset({"black.toml"}), bases=_bases("black.fmt_comment")
    ),
    StarterTool(
        name="pylint",
        files=frozenset({".pylintrc", "pylintrc"}),
        bases=_bases("pylint.disable_comment"),
    ),
    StarterTool(
        name="bandit",
        files=frozenset({".bandit"}),
        bases=_bases("bandit.nosec_comment"),
    ),
    StarterTool(
        name="codespell",
        files=frozenset({".codespellrc"}),
        bases=_bases("codespell.ignore_comment"),
    ),
    StarterTool(
        name="mypy",
        files=frozenset({"mypy.ini", ".mypy.ini"}),
        bases=_bases("mypy.type_ignore_comment"),
    ),
    StarterTool(
        name="pyright",
        files=frozenset({"pyrightconfig.json"}),
        bases=_bases("pyright.ignore_comment"),
    ),
    # basedpyright reads pyright's file and section too, and shares its comment
    StarterTool(
        name="basedpyright", files=frozenset(), bases=_bases("pyright.ignore_comment")
    ),
    StarterTool(
        name="ty", files=frozenset({"ty.toml"}), bases=_bases("ty.ignore_comment")
    ),
    StarterTool(
        name="pytest",
        files=frozenset({"pytest.ini"}),
        bases=_bases("pytest.skip_marks", "pytest.xfail_marks"),
    ),
    StarterTool(
        name="coverage",
        files=frozenset({".coveragerc"}),
        bases=_bases("coverage.pragma_comment"),
    ),
)
