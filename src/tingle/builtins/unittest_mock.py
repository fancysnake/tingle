"""Templates for unittest.mock: the parts of a test suite that assert least."""

from __future__ import annotations

from tingle.pacts.config import MetricTemplate

__all__ = ["any_used", "patch_used"]

any_used = MetricTemplate(
    type="symbol_uses",
    name="mock-any-uses",
    group="testing",
    description="`ANY` placeholders standing in for an assertion.",
    params={"symbol": "ANY"},
)

patch_used = MetricTemplate(
    type="symbol_uses",
    name="mock-patch-uses",
    group="testing",
    description="`mock.patch` uses: tests bound to the shape of the code.",
    params={"symbol": "patch"},
)
