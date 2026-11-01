"""Which tools `tingle init` recognises, and what it starts each one on."""

from __future__ import annotations

from dataclasses import dataclass

from tingle.pacts.config import BUILTIN_TEMPLATE_PACKAGE


@dataclass(frozen=True)
class StarterTool:
    """A tool, the configuration that gives it away, and its starter metrics.

    A file name or a section name is enough, and nothing else counts: a
    tool someone installed but never configured leaves no markers worth a
    metric. The bases are the inline comments only, since those count the
    same wherever the tool keeps its own config.
    """

    files: frozenset[str] = frozenset()
    sections: frozenset[str] = frozenset()
    bases: tuple[str, ...] = ()


def _bases(*paths: str) -> tuple[str, ...]:
    return tuple(f"{BUILTIN_TEMPLATE_PACKAGE}.{path}" for path in paths)


#: In the order the starter lists their metrics.
STARTER_TOOLS = (
    StarterTool(
        files=frozenset({"ruff.toml", ".ruff.toml"}),
        sections=frozenset({"tool.ruff"}),
        bases=_bases("ruff.noqa_comment"),
    ),
    StarterTool(
        files=frozenset({"black.toml"}),
        sections=frozenset({"tool.black"}),
        bases=_bases("black.fmt_comment"),
    ),
    StarterTool(
        files=frozenset({".pylintrc", "pylintrc"}),
        sections=frozenset({"tool.pylint"}),
        bases=_bases("pylint.disable_comment"),
    ),
    StarterTool(
        files=frozenset({".bandit"}),
        sections=frozenset({"tool.bandit"}),
        bases=_bases("bandit.nosec_comment"),
    ),
    StarterTool(
        files=frozenset({".codespellrc"}),
        sections=frozenset({"tool.codespell", "codespell"}),
        bases=_bases("codespell.ignore_comment"),
    ),
    StarterTool(
        files=frozenset({"mypy.ini", ".mypy.ini"}),
        sections=frozenset({"tool.mypy", "mypy"}),
        bases=_bases("mypy.type_ignore_comment"),
    ),
    # basedpyright reads pyright's file and section as well as its own
    StarterTool(
        files=frozenset({"pyrightconfig.json"}),
        sections=frozenset({"tool.pyright", "tool.basedpyright"}),
        bases=_bases("pyright.ignore_comment"),
    ),
    StarterTool(
        files=frozenset({"ty.toml"}),
        sections=frozenset({"tool.ty"}),
        bases=_bases("ty.ignore_comment"),
    ),
    StarterTool(
        files=frozenset({"pytest.ini"}),
        sections=frozenset({"tool.pytest", "pytest", "tool:pytest"}),
        bases=_bases("pytest.skip_marks", "pytest.xfail_marks"),
    ),
    StarterTool(
        files=frozenset({".coveragerc"}),
        sections=frozenset({"tool.coverage", "coverage:run", "coverage:report"}),
        bases=_bases("coverage.pragma_comment"),
    ),
)
