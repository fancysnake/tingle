"""The text of the fix skill: one section per configured metric."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from tingle.pacts.config import MetricSpec

SKILL_NAME = "tingle-fix"

PLACEHOLDER = "_No guidance yet._"

_HEAD = f"""---
name: {SKILL_NAME}
description: >-
  How this project removes the debt its tingle metrics count. Use when
  `tingle check` fails a branch, or when asked to reduce, fix or pay down
  what a tingle metric counts.
---

# Fixing what tingle counts

tingle counts debt markers in this project, and `tingle check` fails a branch
that adds to them. Run `tingle check` to see which metrics the branch grew
and the lines it added. Each metric has a section below, under the name
`tingle check` prints.

## The rule

Change the code until the marker is not needed.

- Leave every finding visible. A suppression comment, an ignore entry or an
  exclusion is the debt tingle counts, so adding one makes the branch worse.
- Leave the tingle config as it is. A change that makes the config count
  less goes in a branch of its own, with nothing else in it, for a person to
  review.
- When you cannot remove a marker, stop and say why. The check stays red.

A metric section that holds `{PLACEHOLDER}` gives no project guidance: the
rule above is all there is.

## Metrics
"""


def render(metrics: Iterable[MetricSpec]) -> str:
    """Write the skill out: the rule, then a placeholder section per metric."""
    return _HEAD + "".join(f"\n{_section(metric)}\n" for metric in metrics)


def _section(metric: MetricSpec) -> str:
    parts = (f"### {metric.name}", metric.description, PLACEHOLDER)
    return "\n\n".join(part for part in parts if part)
