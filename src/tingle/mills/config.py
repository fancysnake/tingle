"""Validation of raw configuration data into a Config."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tingle.pacts.config import Config, ConfigError, MetricSpec, RangeSpec
from tingle.pacts.metrics import MetricType
from tingle.specs.config import (
    IMPLICIT_RANGE_INCLUDE,
    IMPLICIT_RANGE_NAME,
    METRIC_NAME_RE,
)

_TOP_LEVEL_KEYS = frozenset({"ranges", "metrics"})
_RANGE_KEYS = frozenset({"include", "exclude", "default"})
_METRIC_RESERVED_KEYS = frozenset({"name", "type", "range", "ranges"})


def validate(
    raw: Mapping[str, Any],
    metric_types: Mapping[str, MetricType],
    *,
    root: Path,
    source: Path,
) -> Config:
    """Turn raw config data into a Config, or raise ConfigError with every problem."""
    errors: list[str] = []

    for key in sorted(set(raw) - _TOP_LEVEL_KEYS):
        errors.append(f'unknown top-level key "{key}"')

    ranges = _validate_ranges(raw.get("ranges", {}), errors)
    metrics = _validate_metrics(raw.get("metrics", []), metric_types, ranges, errors)
    default_range = _resolve_default_range(ranges, errors)

    if errors:
        raise ConfigError(errors)
    return Config(
        root=root,
        source=source,
        ranges=ranges,
        metrics=metrics,
        default_range=default_range,
    )


def _validate_ranges(raw_ranges: Any, errors: list[str]) -> dict[str, RangeSpec]:
    if not isinstance(raw_ranges, Mapping):
        errors.append("[ranges] must be a table")
        return {}

    ranges: dict[str, RangeSpec] = {}
    for name, table in raw_ranges.items():
        label = f'range "{name}"'
        if not isinstance(table, Mapping):
            errors.append(f"{label}: must be a table")
            continue
        for key in sorted(set(table) - _RANGE_KEYS):
            errors.append(f'{label}: unknown key "{key}"')

        include = _string_list(table.get("include"), f"{label}: include", errors)
        if include is not None and not include:
            errors.append(f"{label}: include must not be empty")
            include = None
        if "include" not in table:
            errors.append(f"{label}: missing include")

        exclude = _string_list(table.get("exclude", []), f"{label}: exclude", errors)

        default = table.get("default", False)
        if not isinstance(default, bool):
            errors.append(f"{label}: default must be a boolean")
            default = False

        if include is not None and exclude is not None:
            ranges[name] = RangeSpec(
                name=name,
                include=tuple(include),
                exclude=tuple(exclude),
                default=default,
            )
    return ranges


def _validate_metrics(
    raw_metrics: Any,
    metric_types: Mapping[str, MetricType],
    ranges: Mapping[str, RangeSpec],
    errors: list[str],
) -> tuple[MetricSpec, ...]:
    if not isinstance(raw_metrics, list):
        errors.append("[[metrics]] must be an array of tables")
        return ()

    metrics: list[MetricSpec] = []
    seen_names: set[str] = set()
    for index, table in enumerate(raw_metrics):
        if not isinstance(table, Mapping):
            errors.append(f"metrics[{index}]: must be a table")
            continue

        name = table.get("name")
        label = f'metric "{name}"' if isinstance(name, str) else f"metrics[{index}]"
        if name is None:
            errors.append(f"{label}: missing name")
        elif not isinstance(name, str):
            errors.append(f"metrics[{index}]: name must be a string")
            name = None
        elif not METRIC_NAME_RE.match(name):
            errors.append(
                f"{label}: invalid name (allowed: letters, digits, '_', '-', '.')"
            )
        elif name in seen_names:
            errors.append(f"{label}: duplicate name")
        else:
            seen_names.add(name)

        range_names = _metric_ranges(table, ranges, label, errors)
        params = {
            key: value
            for key, value in table.items()
            if key not in _METRIC_RESERVED_KEYS
        }

        type_name = table.get("type")
        if type_name is None:
            errors.append(f"{label}: missing type")
            continue
        if not isinstance(type_name, str) or type_name not in metric_types:
            errors.append(f"{label}: unknown type {type_name!r}")
            continue
        _validate_params(metric_types[type_name], params, label, errors)

        if isinstance(name, str):
            metrics.append(
                MetricSpec(
                    name=name, type=type_name, ranges=range_names, params=params
                )
            )
    return tuple(metrics)


def _metric_ranges(
    table: Mapping[str, Any],
    ranges: Mapping[str, RangeSpec],
    label: str,
    errors: list[str],
) -> tuple[str, ...]:
    if "range" in table and "ranges" in table:
        errors.append(f'{label}: give either "range" or "ranges", not both')
        return ()

    if "range" in table:
        single = table["range"]
        if not isinstance(single, str):
            errors.append(f"{label}: range must be a string")
            return ()
        names: list[str] = [single]
    elif "ranges" in table:
        listed = _string_list(table["ranges"], f"{label}: ranges", errors)
        if listed is None:
            return ()
        if not listed:
            errors.append(f"{label}: ranges must not be empty")
            return ()
        names = listed
    else:
        return ()

    for name in names:
        if name not in ranges:
            errors.append(f'{label}: unknown range "{name}"')
    return tuple(names)


def _validate_params(
    metric_type: MetricType,
    params: Mapping[str, Any],
    label: str,
    errors: list[str],
) -> None:
    known = set(metric_type.required_params) | set(metric_type.optional_params)
    for missing in sorted(set(metric_type.required_params) - set(params)):
        errors.append(f'{label}: missing required param "{missing}"')
    for unknown in sorted(set(params) - known):
        errors.append(f'{label}: unknown param "{unknown}"')
    if metric_type.validate_params is not None and set(
        metric_type.required_params
    ) <= set(params):
        errors.extend(
            f"{label}: {problem}" for problem in metric_type.validate_params(params)
        )


def _resolve_default_range(
    ranges: Mapping[str, RangeSpec], errors: list[str]
) -> RangeSpec:
    defaults = [spec for spec in ranges.values() if spec.default]
    if len(defaults) > 1:
        names = ", ".join(sorted(spec.name for spec in defaults))
        errors.append(f"only one range may set default = true (found: {names})")
    if defaults:
        return defaults[0]
    return RangeSpec(name=IMPLICIT_RANGE_NAME, include=IMPLICIT_RANGE_INCLUDE)


def _string_list(value: Any, label: str, errors: list[str]) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not all(
        isinstance(item, str) for item in value
    ):
        errors.append(f"{label} must be a list of strings")
        return None
    return value
