"""Templates for coverage.py: lines the report has been told not to see."""

from __future__ import annotations

from tingle.pacts.config import MetricTemplate

__all__ = ["pragma_comment"]

pragma_comment = MetricTemplate(
    type="regex_count",
    name="pragma-comment",
    group="testing",
    description="`# pragma: no cover` and `no branch`: lines the report skips.",
    # coverage.py's own default exclusions, case and all; any other
    # `# pragma` belongs to some other tool
    params={
        "pattern": r"#\s*pragma[:\s]?\s*no\s*(?:cover|branch)",
        "flags": ["IGNORECASE"],
    },
)
