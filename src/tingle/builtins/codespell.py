"""Templates for codespell: spelling the spellchecker has been told to skip."""

from __future__ import annotations

from tingle.pacts.config import MetricTemplate

__all__ = ["ignore_comment"]

ignore_comment = MetricTemplate(
    type="regex_count",
    name="codespell-comment",
    group="formatting",
    description="`# codespell:ignore` comments that skip the spellchecker.",
    params={"pattern": r"#\s*codespell:ignore"},
)
