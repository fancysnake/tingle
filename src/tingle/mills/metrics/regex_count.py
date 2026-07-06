"""Regex match counting metric."""

import re
from typing import TYPE_CHECKING, Any

from tingle.pacts.diff import DiffMetricContext, DiffResult
from tingle.pacts.metrics import MetricContext, MetricResult

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from collections.abc import Set as AbstractSet

    from tingle.pacts.diff import FileDiff

_FLAGS = {
    "IGNORECASE": re.IGNORECASE,
    "MULTILINE": re.MULTILINE,
    "DOTALL": re.DOTALL,
}


def regex_count(ctx: MetricContext) -> MetricResult:
    """Count matches of the `pattern` param across the context's files."""
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


def regex_count_diff(ctx: DiffMetricContext) -> DiffResult:
    """Count matches on lines the branch added vs lines it removed.

    Diff mode matches line by line with terminators stripped: patterns
    containing newlines never match here, and MULTILINE/DOTALL have no
    cross-line effect. The full-repo total uses full-text matching, so
    the two can disagree for such patterns.
    """
    pattern = _compile(ctx.params)
    added = 0
    removed = 0
    details: dict[str, int] = {}
    warnings: list[str] = []
    for file in ctx.files:
        file_added = _count_on_lines(pattern, ctx.read, file, file.added_lines)
        file_removed = _count_on_lines(
            pattern, ctx.read_base, file, file.removed_lines
        )
        if file_added is None:
            warnings.append(f"{file.path}: current side unreadable")
            file_added = 0
        if file_removed is None:
            warnings.append(f"{file.path}: base side unreadable")
            file_removed = 0
        added += file_added
        removed += file_removed
        if file_added - file_removed:
            details[str(file.path)] = file_added - file_removed
    return DiffResult(
        net=added - removed,
        added=added,
        removed=removed,
        details=details,
        warnings=tuple(warnings),
    )


def _count_on_lines(
    pattern: re.Pattern[str],
    reader: Callable[..., str | None],
    file: FileDiff,
    lines: AbstractSet[int],
) -> int | None:
    """Count matches on the given line numbers; None when text is unreadable."""
    if not lines:
        return 0
    text = reader(file.path)
    if text is None:
        return None
    return sum(
        1
        for lineno, line in enumerate(text.splitlines(), start=1)
        if lineno in lines
        for _ in pattern.finditer(line)
    )


def validate_params(params: Mapping[str, Any]) -> list[str]:
    """Check that `pattern` compiles and `flags` names are known."""
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
