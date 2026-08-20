"""Building and validating a new metric entry for `tingle add`."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tingle.mills.config import validate
from tingle.pacts.config import ConfigError, MetricDraft

if TYPE_CHECKING:
    from tingle.pacts.metrics import MetricType

#: The base table of a metric that builds on nothing.
_NO_BASE: Mapping[str, Any] = {}


def build_metric(
    raw: Mapping[str, Any],
    metric_types: Mapping[str, MetricType],
    *,
    draft: MetricDraft,
    templates: Mapping[str, Mapping[str, Any] | None] | None = None,
) -> dict[str, Any]:
    """Return the metric table to append, or raise ConfigError.

    The candidate is validated against the merged existing config before
    anything is written. A drafted base is written as the base it is, not
    as its expansion: the point of naming a template is that the config
    keeps following it.
    """
    existing_metrics = raw.get("metrics", [])
    if not isinstance(existing_metrics, list):
        raise ConfigError(["[[metrics]] must be an array of tables"])

    type_name, base = _drafted(
        draft, metric_types=metric_types, templates=templates or {}
    )
    all_params = _merge_params(draft, metric_types, type_name=type_name)

    metric: dict[str, Any] = {}
    if draft.base is not None:
        metric["base"] = draft.base
    metric["name"] = draft.name or _drafted_name(
        existing_metrics, draft, type_name=type_name, base=base
    )
    if draft.type_name is not None:
        metric["type"] = draft.type_name
    if draft.group is not None:
        metric["group"] = draft.group
    if draft.description is not None:
        metric["description"] = draft.description
    if len(draft.ranges) == 1:
        metric["range"] = draft.ranges[0]
    elif len(draft.ranges) > 1:
        metric["ranges"] = list(draft.ranges)
    metric.update(all_params)

    merged = {**raw, "metrics": [*existing_metrics, metric]}
    validate(merged, metric_types, source=Path(), templates=templates)
    return metric


def _drafted(
    draft: MetricDraft,
    *,
    metric_types: Mapping[str, MetricType],
    templates: Mapping[str, Mapping[str, Any] | None],
) -> tuple[str, Mapping[str, Any] | None]:
    """Resolve the type the draft means, and the template it builds on.

    Answering both at once is what lets everything downstream stop asking
    which of the two ways round a draft was written: a metric has a type
    whichever of the draft and the template supplied it.
    """
    if draft.base is None:
        if draft.type_name is None:
            msg = "give a metric type, or --base to build on a template"
            raise ConfigError([msg])
        return _known_type(draft.type_name, metric_types), None

    if draft.base not in templates:
        raise ConfigError([f"unknown template {draft.base!r}"])
    # a base that is present but broke was reported by the resolver, and
    # `tingle add` refuses before reaching here; treating it as stating
    # nothing keeps that from needing a branch that cannot be taken
    base = templates[draft.base] or _NO_BASE

    if isinstance(stated := base.get("type"), str):
        if draft.type_name is not None:
            raise ConfigError(
                [f'the base fixes the metric type ("{stated}"); drop the type argument']
            )
        return stated, base
    # a mixin states no type, so the entry has to -- which is the one case
    # where naming a base and a type together is not a contradiction
    if draft.type_name is None:
        raise ConfigError(
            [f"template {draft.base!r} states no type; give one alongside --base"]
        )
    return _known_type(draft.type_name, metric_types), base


def _known_type(type_name: str, metric_types: Mapping[str, MetricType]) -> str:
    if type_name not in metric_types:
        known = ", ".join(sorted(metric_types))
        raise ConfigError([f"unknown metric type {type_name!r} (available: {known})"])
    return type_name


def _merge_params(
    draft: MetricDraft, metric_types: Mapping[str, MetricType], *, type_name: str
) -> dict[str, Any]:
    all_params: dict[str, Any] = dict(draft.params)
    if draft.value is None:
        return all_params

    primary = metric_types[type_name].params.primary
    if primary is None:
        msg = (
            f'metric type "{type_name}" takes no positional value;'
            " use --param key=value"
        )
        raise ConfigError([msg])
    if primary in all_params:
        raise ConfigError(
            [f'param "{primary}" given both positionally and via --param']
        )
    all_params[primary] = draft.value
    return all_params


def _drafted_name(
    existing_metrics: list[Any],
    draft: MetricDraft,
    *,
    type_name: str,
    base: Mapping[str, Any] | None,
) -> str:
    """Name the metric when the draft did not.

    A template that names a metric already answers this, so long as the
    name is free -- and when it is not, the counter that keeps two
    `regex_count` metrics apart keeps two uses of one template apart too.
    """
    if draft.base is not None:
        named = (base or _NO_BASE).get("name")
        return _free(existing_metrics, named if isinstance(named, str) else draft.base)
    return _auto_name(existing_metrics, type_name, value=draft.value)


def _auto_name(
    existing_metrics: list[Any], type_name: str, *, value: str | None
) -> str:
    base = f"{type_name}-{_slug(value)}" if value else type_name
    return _free(existing_metrics, base)


def _free(existing_metrics: list[Any], base: str) -> str:
    taken = {
        entry.get("name") for entry in existing_metrics if isinstance(entry, Mapping)
    }
    candidate = base
    counter = 2
    while candidate in taken:
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-.").lower()
    return cleaned or "metric"
