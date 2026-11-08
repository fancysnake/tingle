"""Comparing a branch's config with the one its base holds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tingle.pacts.check import Loosening
from tingle.pacts.config import CheckPolicy

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import PurePath

    from tingle.pacts.config import Config, MetricSpec
    from tingle.pacts.metrics import MetricType


@dataclass(frozen=True)
class Scores:
    """The branch's tree measured under the base's config, then under its own."""

    before: Mapping[str, int]
    after: Mapping[str, int]


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
    scores: Scores,
    modules: tuple[PurePath, ...] = (),
) -> tuple[Loosening, ...]:
    """Every way `own` weakens the gate `base` set up.

    `scores` measures one tree under both configs, so only the config can
    have moved a number. A metric that answered under one and not the other
    is not compared. `modules` are
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
    before, after = scores.before, scores.after
    for spec in judged:
        name = spec.name
        if name not in names:
            found.append(Loosening(name, "removed"))
        elif name in own.check.ignore:
            found.append(Loosening(name, "moved to [check] ignore"))
        elif name in before and name in after and after[name] < before[name]:
            found.append(Loosening(name, f"{before[name]} to {after[name]}"))
    return (*found, *module_loosenings(modules))


def module_loosenings(modules: Iterable[PurePath]) -> tuple[Loosening, ...]:
    """Report each template module the branch changed."""
    return tuple(Loosening(str(path), "template module changed") for path in modules)


def changed_modules(
    bases: Iterable[str], changed: Iterable[PurePath]
) -> tuple[PurePath, ...]:
    """Pick the changed files that dotted template `bases` run through.

    The files are told from the paths alone, because a deleted module no
    longer imports to say where it was.
    """
    dotted = [tuple(base.split(".")[:-1]) for base in bases]
    return tuple(
        path
        for path in changed
        if path.suffix == ".py" and any(_reaches(mods, path) for mods in dotted)
    )


def _reaches(modules: tuple[str, ...], path: PurePath) -> bool:
    """Whether `path` ends in the file of a module along dotted `modules`.

    Only the tail is compared, so `src/pack/rules.py` is `pack.rules`
    wherever the package root sits.
    """
    # shortcut: a package mapped onto a directory of another name is missed,
    # ask the template loader first if one turns up
    parts = path.with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return any(
        parts[-depth:] == modules[:depth] for depth in range(1, len(modules) + 1)
    )
