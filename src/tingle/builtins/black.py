"""Templates for black: code the formatter has been told to leave alone."""

from __future__ import annotations

from tingle.pacts.config import MetricTemplate

__all__ = ["fmt_comment", "fmt_spread"]

fmt_comment = MetricTemplate(
    type="regex_count",
    name="fmt-comment",
    group="formatting",
    description="`# fmt` comments that switch off the formatter.",
    params={"pattern": r"#\s*fmt"},
)

fmt_spread = MetricTemplate(
    type="regex_spread",
    name="fmt-spread",
    group="formatting",
    description="Files carrying a `# fmt` comment, however many each holds.",
    params={"pattern": r"#\s*fmt"},
)
