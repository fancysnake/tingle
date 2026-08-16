"""Templates for ruff: silenced rules, inline and project-wide."""

from __future__ import annotations

from tingle.pacts.config import MetricTemplate

__all__ = [
    "format_excludes",
    "lint_ignores",
    "noqa_comment",
    "noqa_spread",
    "per_file_ignores",
]

noqa_comment = MetricTemplate(
    type="regex_count",
    name="noqa-comment",
    group="linting",
    description="`# noqa:` comments that silence a ruff rule on one line.",
    params={"pattern": r"#\s*noqa:"},
)

noqa_spread = MetricTemplate(
    type="regex_spread",
    name="noqa-spread",
    group="linting",
    description="Files carrying a `# noqa:`, however many each holds.",
    params={"pattern": r"#\s*noqa:"},
)

lint_ignores = MetricTemplate(
    type="toml_list_length",
    name="ruff-ignores",
    group="linting",
    description="Ruff lint rules disabled project-wide.",
    params={"key": "tool.ruff.lint.ignore"},
)

per_file_ignores = MetricTemplate(
    type="toml_list_length",
    name="ruff-per-file-ignores",
    group="linting",
    description="Ruff lint rules disabled for specific files.",
    params={"key": "tool.ruff.lint.per-file-ignores"},
)

format_excludes = MetricTemplate(
    type="toml_list_length",
    name="ruff-format-ignore",
    group="formatting",
    description="Files excluded from ruff formatting.",
    params={"key": "tool.ruff.format.ignore"},
)
