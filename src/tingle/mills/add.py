"""Building and validating a new metric entry for `tingle add`."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tingle.mills.config import validate
from tingle.pacts.config import ConfigError, MetricDraft

if TYPE_CHECKING:
    from tingle.pacts.config import MetricTemplate
    from tingle.pacts.metrics import MetricType


def build_metric(
    raw: Mapping[str, Any],
    metric_types: Mapping[str, MetricType],
    *,
    draft: MetricDraft,
    templates: Mapping[str, MetricTemplate] | None = None,
) -> dict[str, Any]:
    """Return the metric table to append, or raise ConfigError.

    The candidate is validated against the merged existing config before
    anything is written. A drafted base is written as the base it is, not
    as its expansion: the point of naming a template is that the config
    keeps following it.
    """
    template = _drafted_template(
        draft, metric_types=metric_types, templates=templates or {}
    )
    existing_metrics = raw.get("metrics", [])
    if not isinstance(existing_metrics, list):
        raise ConfigError(["[[metrics]] must be an array of tables"])

    all_params = _merge_params(draft, metric_types, template=template)

    metric: dict[str, Any] = {}
    if draft.base is not None:
        metric["base"] = draft.base
    metric["name"] = draft.name or _drafted_name(
        existing_metrics, draft, template=template
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
    validate(merged, metric_types, root=Path(), source=Path(), templates=templates)
    return metric


def _drafted_template(
    draft: MetricDraft,
    *,
    metric_types: Mapping[str, MetricType],
    templates: Mapping[str, MetricTemplate],
) -> MetricTemplate | None:
    """Resolve what the draft says it is building on, or raise ConfigError."""
    if draft.type_name is not None and draft.base is not None:
        raise ConfigError(["give either a metric type or --base, not both"])
    if draft.type_name is None and draft.base is None:
        raise ConfigError(["give a metric type, or --base to build on a template"])
    if draft.base is not None:
        if (template := templates.get(draft.base)) is None:
            raise ConfigError([f"unknown template {draft.base!r}"])
        return template
    if draft.type_name not in metric_types:
        known = ", ".join(sorted(metric_types))
        raise ConfigError(
            [f"unknown metric type {draft.type_name!r} (available: {known})"]
        )
    return None


def _merge_params(
    draft: MetricDraft,
    metric_types: Mapping[str, MetricType],
    *,
    template: MetricTemplate | None,
) -> dict[str, Any]:
    all_params: dict[str, Any] = dict(draft.params)
    if draft.value is None:
        return all_params

    type_name = draft.type_name if template is None else template.type
    known = metric_types.get(type_name) if type_name is not None else None
    primary = known.params.primary if known is not None else None
    if primary is None:
        subject = f'metric type "{draft.type_name}"' if template is None else "the base"
        raise ConfigError(
            [f"{subject} takes no positional value; use --param key=value"]
        )
    if primary in all_params:
        raise ConfigError(
            [f'param "{primary}" given both positionally and via --param']
        )
    all_params[primary] = draft.value
    return all_params


def _drafted_name(
    existing_metrics: list[Any], draft: MetricDraft, *, template: MetricTemplate | None
) -> str:
    """Name the metric when the draft did not.

    A template that names a metric already answers this, so long as the
    name is free -- and when it is not, the counter that keeps two
    `regex_count` metrics apart keeps two uses of one template apart too.
    """
    if template is not None:
        return _free(existing_metrics, template.name or draft.base or "metric")
    return _auto_name(existing_metrics, draft.type_name or "metric", value=draft.value)


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
