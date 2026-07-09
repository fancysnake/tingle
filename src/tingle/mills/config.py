"""Validation of raw configuration data into a Config."""
from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from tingle.pacts.config import Config, ConfigError, MetricSpec, RangeSpec
from tingle.specs.config import (
    IMPLICIT_RANGE_INCLUDE,
    IMPLICIT_RANGE_NAME,
    METRIC_NAME_RE,
)

if TYPE_CHECKING:
    from pathlib import Path

    from tingle.pacts.metrics import MetricType

_TOP_LEVEL_KEYS = frozenset({"ranges", "metrics", "diff"})
_DIFF_KEYS = frozenset({"base"})
_RANGE_KEYS = frozenset({"include", "exclude", "default"})
_METRIC_RESERVED_KEYS = frozenset({"name", "type", "range", "ranges", "group"})


def validate(
    raw: Mapping[str, Any],
    metric_types: Mapping[str, MetricType],
    *,
    root: Path,
    source: Path,
) -> Config:
    """Turn raw config data into a Config, or raise ConfigError with every problem."""
    errors: list[str] = []
    errors.extend(
        f'unknown top-level key "{key}"'
        for key in sorted(set(raw) - _TOP_LEVEL_KEYS)
    )

    ranges = _validate_ranges(raw.get("ranges", {}), errors)
    metrics = _validate_metrics(raw.get("metrics", []), metric_types, ranges, errors)
    default_range = _resolve_default_range(ranges, errors)
    diff_base = _validate_diff(raw.get("diff", {}), errors)

    if errors:
        raise ConfigError(errors)
    return Config(
        root=root,
        source=source,
        ranges=ranges,
        metrics=metrics,
        default_range=default_range,
        diff_base=diff_base,
    )


def _validate_ranges(raw_ranges: object, errors: list[str]) -> dict[str, RangeSpec]:
    if not isinstance(raw_ranges, Mapping):
        errors.append("[ranges] must be a table")
        return {}

    ranges: dict[str, RangeSpec] = {}
    for name, table in raw_ranges.items():
        label = f'range "{name}"'
        if not isinstance(table, Mapping):
            errors.append(f"{label}: must be a table")
            continue
        errors.extend(
            f'{label}: unknown key "{key}"'
            for key in sorted(set(table) - _RANGE_KEYS)
        )

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
    raw_metrics: object,
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

        name, label = _metric_name(table, index, seen_names, errors)
        range_names = _metric_ranges(table, ranges, label, errors)
        group = _metric_group(table, label, errors)
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

        if name is not None:
            metrics.append(
                MetricSpec(
                    name=name,
                    type=type_name,
                    ranges=range_names,
                    params=params,
                    group=group,
                )
            )
    return tuple(metrics)


def _metric_group(
    table: Mapping[str, Any], label: str, errors: list[str]
) -> str | None:
    """Validate the optional `group`.

    A human-facing heading, so any non-empty string is allowed (unlike
    names, which METRIC_NAME_RE constrains).
    """
    if "group" not in table:
        return None
    group = table["group"]
    if not isinstance(group, str) or not group:
        errors.append(f"{label}: group must be a non-empty string")
        return None
    return group


def _metric_name(
    table: Mapping[str, Any],
    index: int,
    seen_names: set[str],
    errors: list[str],
) -> tuple[str | None, str]:
    """Validate a metric's name; return it (or None) plus the error label."""
    name = table.get("name")
    label = f'metric "{name}"' if isinstance(name, str) else f"metrics[{index}]"
    if name is None:
        errors.append(f"{label}: missing name")
        return None, label
    if not isinstance(name, str):
        errors.append(f"{label}: name must be a string")
        return None, label
    if not METRIC_NAME_RE.match(name):
        errors.append(
            f"{label}: invalid name (allowed: letters, digits, '_', '-', '.')"
        )
    elif name in seen_names:
        errors.append(f"{label}: duplicate name")
    else:
        seen_names.add(name)
    return name, label


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

    errors.extend(
        f'{label}: unknown range "{name}"' for name in names if name not in ranges
    )
    return tuple(names)


def _validate_params(
    metric_type: MetricType,
    params: Mapping[str, Any],
    label: str,
    errors: list[str],
) -> None:
    known = set(metric_type.required_params) | set(metric_type.optional_params)
    errors.extend(
        f'{label}: missing required param "{missing}"'
        for missing in sorted(set(metric_type.required_params) - set(params))
    )
    errors.extend(
        f'{label}: unknown param "{unknown}"'
        for unknown in sorted(set(params) - known)
    )
    if metric_type.validate_params is not None and set(
        metric_type.required_params
    ) <= set(params):
        errors.extend(
            f"{label}: {problem}" for problem in metric_type.validate_params(params)
        )


def _validate_diff(raw_diff: object, errors: list[str]) -> str | None:
    if not isinstance(raw_diff, Mapping):
        errors.append("[diff] must be a table")
        return None
    errors.extend(
        f'[diff]: unknown key "{key}"' for key in sorted(set(raw_diff) - _DIFF_KEYS)
    )
    base = raw_diff.get("base")
    if base is not None and not isinstance(base, str):
        errors.append("[diff]: base must be a string")
        return None
    return base


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


def _string_list(value: object, label: str, errors: list[str]) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not all(
        isinstance(item, str) for item in value
    ):
        errors.append(f"{label} must be a list of strings")
        return None
    return value
