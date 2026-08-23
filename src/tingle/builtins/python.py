"""Templates for the language itself, no tool required."""

from __future__ import annotations

from tingle.pacts.config import MetricTemplate

__all__ = ["any_used", "cast_used", "long_files", "object_used", "todo_comments"]

any_used = MetricTemplate(
    type="symbol_uses",
    name="any-uses",
    group="typing",
    description="`typing.Any`: the escape hatch from every other type.",
    params={"symbol": "typing.Any"},
)

cast_used = MetricTemplate(
    type="symbol_uses",
    name="cast-uses",
    group="typing",
    description="`typing.cast`: a type asserted where it could not be inferred.",
    params={"symbol": "typing.cast"},
)

object_used = MetricTemplate(
    type="symbol_uses",
    name="object-uses",
    group="typing",
    description="`object` annotations: a type saying only that a value exists.",
    params={"symbol": "object"},
)

todo_comments = MetricTemplate(
    type="regex_count",
    name="todo-comments",
    group="linting",
    description="`TODO`, `FIXME`, `XXX` and `HACK`: work written down, not done.",
    params={"pattern": r"#\s*(TODO|FIXME|XXX|HACK)\b"},
)

long_files = MetricTemplate(
    type="file_count",
    name="long-files",
    group="linting",
    description="Files over 1000 lines.",
    params={"over_lines": 1000},
)
