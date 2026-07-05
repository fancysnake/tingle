"""Regex match counting metric."""

import re
from collections.abc import Mapping
from typing import Any

from tingle.pacts.metrics import MetricContext, MetricResult

_FLAGS = {
    "IGNORECASE": re.IGNORECASE,
    "MULTILINE": re.MULTILINE,
    "DOTALL": re.DOTALL,
}


def regex_count(ctx: MetricContext) -> MetricResult:
    pattern = _compile(ctx.params)
    total = 0
    details: dict[str, int] = {}
    warnings: list[str] = []
    for path in ctx.files:
        text = ctx.read(path)
        if text is None:
            warnings.append(f"{path}: skipped (binary, unreadable, or missing)")
            continue
        count = sum(1 for _ in pattern.finditer(text))
        if count:
            details[str(path)] = count
        total += count
    return MetricResult(value=total, details=details, warnings=tuple(warnings))


def validate_params(params: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []

    pattern = params.get("pattern")
    if not isinstance(pattern, str):
        errors.append("pattern must be a string")
    else:
        try:
            re.compile(pattern)
        except re.error as exc:
            errors.append(f"invalid pattern: {exc}")

    flags = params.get("flags", [])
    if not isinstance(flags, list) or not all(
        isinstance(flag, str) for flag in flags
    ):
        errors.append("flags must be a list of strings")
    else:
        allowed = ", ".join(sorted(_FLAGS))
        errors.extend(
            f"unknown flag {flag!r} (allowed: {allowed})"
            for flag in flags
            if flag not in _FLAGS
        )
    return errors


def _compile(params: Mapping[str, Any]) -> re.Pattern[str]:
    flags = re.NOFLAG
    for name in params.get("flags", []):
        flags |= _FLAGS[name]
    return re.compile(params["pattern"], flags)
