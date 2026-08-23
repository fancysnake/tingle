"""Templates for ruff: silenced rules, by how much of the file they cover.

Ruff suppresses at four widths -- one line, one range, one file, the
project -- and they are separate templates because they are separate debts.
A `# noqa` on the line that earned it is not the same admission as a
`# ruff: noqa` at the top of a module.
"""

from __future__ import annotations

from tingle.pacts.config import MetricTemplate

__all__ = [
    "file_exemptions",
    "format_excludes",
    "ignore_comment",
    "lint_ignores",
    "noqa_comment",
    "noqa_spread",
    "per_file_ignores",
    "suppressed_ranges",
]

noqa_comment = MetricTemplate(
    type="regex_count",
    name="noqa-comment",
    group="linting",
    description="`# noqa` comments that silence ruff on one line.",
    params={"pattern": r"#\s*noqa"},
)

noqa_spread = MetricTemplate(
    type="regex_spread",
    name="noqa-spread",
    group="linting",
    description="Files carrying a `# noqa`, however many each holds.",
    params={"pattern": r"#\s*noqa"},
)

ignore_comment = MetricTemplate(
    type="regex_count",
    name="ruff-ignore-comment",
    group="linting",
    description="`# ruff: ignore[...]` comments covering a line or a statement.",
    params={"pattern": r"#\s*ruff:\s*ignore\["},
)

# The closing `enable` comment is not counted: one range is one admission,
# and an implicit range has no closing comment to count anyway.
suppressed_ranges = MetricTemplate(
    type="regex_count",
    name="ruff-suppressed-ranges",
    group="linting",
    description="`# ruff: disable[...]` comments switching rules off over a block.",
    params={"pattern": r"#\s*ruff:\s*disable\["},
)

file_exemptions = MetricTemplate(
    type="regex_count",
    name="ruff-file-exemptions",
    group="linting",
    description="Comments exempting a whole file: `# ruff: noqa` or `file-ignore`.",
    params={"pattern": r"#\s*ruff:\s*(?:noqa|file-ignore\[)"},
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
    name="ruff-format-excludes",
    group="formatting",
    description="Files excluded from ruff formatting.",
    params={"key": "tool.ruff.format.exclude"},
)
