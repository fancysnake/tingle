"""Templates for pytest: tests that are declared instead of run."""

from __future__ import annotations

from tingle.pacts.config import MetricTemplate

__all__ = ["skip_marks", "xfail_marks"]

skip_marks = MetricTemplate(
    type="regex_count",
    name="pytest-skip",
    group="testing",
    description="`mark.skip` marks: tests that never run.",
    # `mark.skipif` runs whenever its condition is false, so the boundary
    # keeps a conditional skip out of a count of tests that never run.
    params={"pattern": r"mark\.skip\b"},
)

xfail_marks = MetricTemplate(
    type="regex_count",
    name="pytest-xfail",
    group="testing",
    description="`mark.xfail` marks: failures written down instead of fixed.",
    params={"pattern": r"mark\.xfail"},
)
