"""Templates for mypy: silenced errors, inline and per module."""

from __future__ import annotations

from tingle.pacts.config import MetricTemplate

__all__ = [
    "disabled_error_codes",
    "overrides",
    "type_ignore_comment",
    "type_ignore_spread",
]

type_ignore_comment = MetricTemplate(
    type="regex_count",
    name="type-ignores",
    group="typing",
    description="`# type: ignore` comments that silence the type checker.",
    params={"pattern": r"#\s*type:\s*ignore"},
)

type_ignore_spread = MetricTemplate(
    type="regex_spread",
    name="type-ignore-spread",
    group="typing",
    description="Files carrying a `# type: ignore`, however many each holds.",
    params={"pattern": r"#\s*type:\s*ignore"},
)

overrides = MetricTemplate(
    type="toml_table_array",
    name="mypy-overrides",
    group="typing",
    description="Modules given relaxed mypy strictness.",
    params={"key": "tool.mypy.overrides", "label": "module"},
)

disabled_error_codes = MetricTemplate(
    type="toml_list_length",
    name="mypy-disabled-codes",
    group="typing",
    description="Mypy error codes disabled project-wide.",
    params={"key": "tool.mypy.disable_error_code"},
)
