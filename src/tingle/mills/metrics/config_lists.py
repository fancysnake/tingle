"""List-length metrics over TOML and INI config files.

These are the generic building blocks for counting ignored lint rules:
point them at whatever config file and key/option a linter actually uses.
"""
from __future__ import annotations

import configparser
import tomllib
from collections.abc import Callable, Mapping
from pathlib import PurePath
from typing import Any, TypeAlias

from tingle.pacts.diff import DiffMetricContext, DiffResult
from tingle.pacts.metrics import MetricContext, MetricResult
from tingle.specs.config import TOML_LIST_DEFAULT_FILE

_Reader: TypeAlias = Callable[[PurePath], str | None]


def toml_list_length(ctx: MetricContext) -> MetricResult:
    """Length of the list at the dotted `key` in a TOML `file`."""
    return _toml_count(ctx.read, ctx.params)


def toml_list_length_diff(ctx: DiffMetricContext) -> DiffResult:
    """Change in the list's length between the merge-base and now."""
    return _delta(_toml_count, ctx)


def ini_list_length_diff(ctx: DiffMetricContext) -> DiffResult:
    """Change in the option's entry count between the merge-base and now."""
    return _delta(_ini_count, ctx)


def _delta(
    count: Callable[[_Reader, Mapping[str, Any]], MetricResult],
    ctx: DiffMetricContext,
) -> DiffResult:
    base = count(ctx.read_base, ctx.params)
    current = count(ctx.read, ctx.params)
    warnings = (
        *(f"base side: {warning}" for warning in base.warnings),
        *current.warnings,
    )
    return DiffResult(
        net=current.value - base.value,
        details={"base": base.value, "current": current.value},
        warnings=warnings,
    )


def _toml_count(read: _Reader, params: Mapping[str, Any]) -> MetricResult:
    file = params.get("file", TOML_LIST_DEFAULT_FILE)
    key = params["key"]

    text = read(PurePath(file))
    if text is None:
        return _empty(f"{file}: not found or unreadable")
    try:
        data: Any = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        return _empty(f"{file}: invalid TOML: {exc}")

    for part in key.split("."):
        if not (isinstance(data, Mapping) and part in data):
            return _empty(f'{file}: key "{key}" not found')
        data = data[part]

    if isinstance(data, list):
        return MetricResult(value=len(data))
    if isinstance(data, Mapping) and all(
        isinstance(value, list) for value in data.values()
    ):
        details = {str(name): len(value) for name, value in data.items()}
        return MetricResult(value=sum(details.values()), details=details)
    return _empty(f'{file}: value at "{key}" is not a list or a table of lists')


def validate_toml_params(params: Mapping[str, Any]) -> list[str]:
    """Check `key` is a non-empty string and `file` (if given) a string."""
    errors: list[str] = []
    key = params.get("key")
    if not isinstance(key, str) or not key:
        errors.append("key must be a non-empty string")
    if "file" in params and not isinstance(params["file"], str):
        errors.append("file must be a string")
    return errors


def ini_list_length(ctx: MetricContext) -> MetricResult:
    """Count comma/newline separated entries of `option` in `section`."""
    return _ini_count(ctx.read, ctx.params)


def _ini_count(read: _Reader, params: Mapping[str, Any]) -> MetricResult:
    file = params["file"]
    section = params["section"]
    option = params["option"]

    text = read(PurePath(file))
    if text is None:
        return _empty(f"{file}: not found or unreadable")

    parser = configparser.ConfigParser()
    try:
        parser.read_string(text)
    except configparser.Error as exc:
        return _empty(f"{file}: invalid INI: {exc}")

    if not parser.has_section(section):
        return _empty(f'{file}: section "{section}" not found')
    value = parser.get(section, option, fallback=None)
    if value is None:
        return _empty(f'{file}: option "{option}" not found in "{section}"')

    entries = [
        entry.strip()
        for entry in value.replace(",", "\n").splitlines()
        if entry.strip()
    ]
    return MetricResult(value=len(entries))


def validate_ini_params(params: Mapping[str, Any]) -> list[str]:
    """Check `file`, `section`, and `option` are strings."""
    return [
        f"{name} must be a string"
        for name in ("file", "section", "option")
        if name in params and not isinstance(params[name], str)
    ]


def _empty(warning: str) -> MetricResult:
    return MetricResult(value=0, warnings=(warning,))
