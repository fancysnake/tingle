"""Comparing a branch's config with the one its base holds."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tingle.pacts.check import Loosening
from tingle.pacts.config import CheckPolicy

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import PurePath

    from tingle.pacts.config import Config, MetricSpec
    from tingle.pacts.metrics import MetricType


def judged_at_base(
    base: Config, metric_types: Mapping[str, MetricType]
) -> tuple[MetricSpec, ...]:
    """Select the metrics the base's check takes account of.

    A metric the base ignores, or one with no diff variant, never decided
    a check, so changing it weakens nothing.
    """
    return tuple(
        spec
        for spec in base.metrics
        if spec.name not in base.check.ignore
        and metric_types[spec.type].diff_func is not None
    )


def loosenings(
    base: Config,
    own: Config,
    *,
    judged: tuple[MetricSpec, ...],
    scores: tuple[Mapping[str, int], Mapping[str, int]],
    modules: tuple[PurePath, ...] = (),
) -> tuple[Loosening, ...]:
    """Every way `own` weakens the gate `base` set up.

    `scores` holds the branch's tree measured under `base`, then under
    `own`, so only the config can have moved a number. A metric that
    answered under one and not the other is not compared. `modules` are
    the template modules the branch changed: nothing older than the
    installed tree can be imported to measure them against, so a change is
    all that can be said of one.
    """
    found: list[Loosening] = []
    if base.check.strict and not own.check.strict:
        found.append(Loosening("[check] strict", "turned off"))
    if base.check.policy is CheckPolicy.ANY and own.check.policy is CheckPolicy.SUM:
        found.append(Loosening("[check] policy", "any to sum"))
    names = {spec.name for spec in own.metrics}
    before, after = scores
    for spec in judged:
        name = spec.name
        if name not in names:
            found.append(Loosening(name, "removed"))
        elif name in own.check.ignore:
            found.append(Loosening(name, "moved to [check] ignore"))
        elif name in before and name in after and after[name] < before[name]:
            found.append(Loosening(name, f"{before[name]} to {after[name]}"))
    found.extend(Loosening(str(path), "template module changed") for path in modules)
    return tuple(found)
