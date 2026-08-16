"""Templates for the language itself, no tool required."""

from __future__ import annotations

from tingle.pacts.config import MetricTemplate

__all__ = ["any_used", "long_files", "todo_comments"]

any_used = MetricTemplate(
    type="symbol_uses",
    name="any-uses",
    group="typing",
    description="`typing.Any`: the escape hatch from every other type.",
    params={"symbol": "typing.Any"},
)

todo_comments = MetricTemplate(
    type="regex_count",
    name="todo-comments",
    group="linting",
    description="`TODO` and `FIXME` comments: work written down, not done.",
    params={"pattern": r"#\s*(TODO|FIXME)\b"},
)

long_files = MetricTemplate(
    type="file_count",
    name="long-files",
    group="linting",
    description="Files over 1000 lines.",
    params={"over_lines": 1000},
)
