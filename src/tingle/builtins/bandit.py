"""Templates for bandit: security findings waved through."""

from __future__ import annotations

from tingle.pacts.config import MetricTemplate

__all__ = ["nosec_comment"]

nosec_comment = MetricTemplate(
    type="regex_count",
    name="nosec-comment",
    group="linting",
    description="`# nosec` comments that silence a security check.",
    params={"pattern": r"#\s*nosec\b"},
)
