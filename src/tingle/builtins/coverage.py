"""Templates for coverage.py: lines the report has been told not to see."""

from __future__ import annotations

from tingle.pacts.config import MetricTemplate

__all__ = ["pragma_comment"]

pragma_comment = MetricTemplate(
    type="regex_count",
    name="pragma-comment",
    group="testing",
    description="`# pragma` comments that keep a line out of the report.",
    params={"pattern": r"#\s*pragma"},
)
