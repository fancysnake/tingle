"""Templates for taplo: TOML the formatter has been told to leave alone."""

from __future__ import annotations

from tingle.pacts.config import MetricTemplate

__all__ = ["ignore_comment"]

ignore_comment = MetricTemplate(
    type="regex_count",
    name="taplo-comment",
    group="formatting",
    description="`# taplo:` comments that switch off TOML formatting.",
    params={"pattern": r"#\s*taplo:"},
)
