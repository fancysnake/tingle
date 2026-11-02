"""Templates for ty: diagnostics silenced inline."""

from __future__ import annotations

from tingle.pacts.config import MetricTemplate

__all__ = ["ignore_comment"]

ignore_comment = MetricTemplate(
    type="regex_count",
    name="ty-ignores",
    group="typing",
    description="`# ty: ignore` comments that silence the type checker.",
    params={"pattern": r"#\s*ty:\s*ignore"},
)
