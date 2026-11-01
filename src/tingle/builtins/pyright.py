"""Templates for pyright and basedpyright, which share the comment syntax."""

from __future__ import annotations

from tingle.pacts.config import MetricTemplate

__all__ = ["ignore_comment"]

ignore_comment = MetricTemplate(
    type="regex_count",
    name="pyright-ignores",
    group="typing",
    description="`# pyright: ignore` comments that silence the type checker.",
    params={"pattern": r"#\s*pyright:\s*ignore"},
)
