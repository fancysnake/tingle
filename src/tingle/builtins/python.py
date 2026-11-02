"""Templates for the language itself, no tool required."""

from __future__ import annotations

from tingle.pacts.config import MetricTemplate

__all__ = ["any_used", "cast_used", "deprecated_marks", "long_files", "todo_comments"]

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

# a regex, not `symbol_uses`: `warnings`, `typing_extensions` and the
# `deprecated` package each ship the decorator, and a project may use any
deprecated_marks = MetricTemplate(
    type="regex_count",
    name="deprecated-marks",
    group="architecture",
    description="`@deprecated` decorators: code marked for removal, not removed.",
    params={"pattern": r"^\s*@(?:\w+\.)*deprecated\b", "flags": ["MULTILINE"]},
)
