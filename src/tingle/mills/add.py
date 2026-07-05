"""Building and validating a new metric entry for `tingle add`."""

import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tingle.mills.config import validate
from tingle.pacts.config import ConfigError
from tingle.pacts.metrics import MetricType


def build_metric(
    raw: Mapping[str, Any],
    metric_types: Mapping[str, MetricType],
    type_name: str,
    value: str | None = None,
    name: str | None = None,
    ranges: Sequence[str] = (),
    params: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return the metric table to append, or raise ConfigError.

    The candidate is validated against the merged existing config before
    anything is written.
    """
    if type_name not in metric_types:
        known = ", ".join(sorted(metric_types))
        raise ConfigError(
            [f"unknown metric type {type_name!r} (available: {known})"]
        )
    existing_metrics = raw.get("metrics", [])
    if not isinstance(existing_metrics, list):
        raise ConfigError(["[[metrics]] must be an array of tables"])

    all_params: dict[str, Any] = dict(params or {})
    if value is not None:
        primary = metric_types[type_name].primary_param
        if primary is None:
            raise ConfigError(
                [
                    f'metric type "{type_name}" takes no positional value;'
                    " use --param key=value"
                ]
            )
        if primary in all_params:
            raise ConfigError(
                [f'param "{primary}" given both positionally and via --param']
            )
        all_params[primary] = value

    metric: dict[str, Any] = {
        "name": name or _auto_name(existing_metrics, type_name, value),
        "type": type_name,
    }
    if len(ranges) == 1:
        metric["range"] = ranges[0]
    elif len(ranges) > 1:
        metric["ranges"] = list(ranges)
    metric.update(all_params)

    merged = {**raw, "metrics": [*existing_metrics, metric]}
    validate(merged, metric_types, root=Path(), source=Path())
    return metric


def _auto_name(
    existing_metrics: list[Any], type_name: str, value: str | None
) -> str:
    base = f"{type_name}-{_slug(value)}" if value else type_name
    taken = {
        entry.get("name")
        for entry in existing_metrics
        if isinstance(entry, Mapping)
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
