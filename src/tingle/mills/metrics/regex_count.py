"""Regex match counting metric."""

from __future__ import annotations

import re
from bisect import bisect_right
from typing import TYPE_CHECKING, Any

from tingle.pacts.diff import DiffMetricContext, DiffResult
from tingle.pacts.metrics import MetricContext, MetricResult, Occurrence

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from collections.abc import Set as AbstractSet

    from tingle.pacts.diff import FileDiff

_FLAGS = {"IGNORECASE": re.IGNORECASE, "MULTILINE": re.MULTILINE, "DOTALL": re.DOTALL}


def regex_count(ctx: MetricContext) -> MetricResult:
    """Count matches of the `pattern` param across the context's files.

    Matching is full-text (multi-line patterns work); each match is
    located at the line where it starts.
    """
    pattern = _compile(ctx.params)
    details: dict[str, int] = {}
    warnings: list[str] = []
    occurrences: list[Occurrence] = []
    for path in ctx.files:
        text = ctx.read(path)
        if text is None:
            warnings.append(f"{path}: skipped (binary, unreadable, or missing)")
            continue
        line_starts = _line_starts(text)
        found = [
            Occurrence(path=str(path), line=bisect_right(line_starts, match.start()))
            for match in pattern.finditer(text)
        ]
        if found:
            details[str(path)] = len(found)
            occurrences.extend(found)
    return MetricResult(
        value=len(occurrences),
        details=details,
        warnings=tuple(warnings),
        occurrences=tuple(occurrences),
    )


def _line_starts(text: str) -> list[int]:
    """Offsets where each line begins; bisect_right(starts, i) is i's line."""
    starts = [0]
    starts.extend(match.end() for match in re.finditer("\n", text))
    return starts


def regex_count_diff(ctx: DiffMetricContext) -> DiffResult:
    """Count matches on lines the branch added vs lines it removed.

    Diff mode matches line by line with terminators stripped: patterns
    containing newlines never match here, and MULTILINE/DOTALL have no
    cross-line effect. The full-repo total uses full-text matching, so
    the two can disagree for such patterns.
    """
    pattern = _compile(ctx.params)
    added_occurrences: list[Occurrence] = []
    removed_occurrences: list[Occurrence] = []
    details: dict[str, int] = {}
    warnings: list[str] = []
    for file in ctx.files:
        file_added = _matches_on_lines(pattern, ctx.read, file, file.added_lines)
        file_removed = _matches_on_lines(
            pattern, ctx.read_base, file, file.removed_lines
        )
        if file_added is None:
            warnings.append(f"{file.path}: current side unreadable")
            file_added = []
        if file_removed is None:
            warnings.append(f"{file.path}: base side unreadable")
            file_removed = []
        added_occurrences.extend(file_added)
        removed_occurrences.extend(file_removed)
        if len(file_added) - len(file_removed):
            details[str(file.path)] = len(file_added) - len(file_removed)
    return DiffResult(
        net=len(added_occurrences) - len(removed_occurrences),
        added=len(added_occurrences),
        removed=len(removed_occurrences),
        details=details,
        warnings=tuple(warnings),
        added_occurrences=tuple(added_occurrences),
        removed_occurrences=tuple(removed_occurrences),
    )


def _matches_on_lines(
    pattern: re.Pattern[str],
    reader: Callable[..., str | None],
    file: FileDiff,
    lines: AbstractSet[int],
) -> list[Occurrence] | None:
    """Locate matches on the given line numbers; None when text is unreadable."""
    if not lines:
        return []
    text = reader(file.path)
    if text is None:
        return None
    return [
        Occurrence(path=str(file.path), line=lineno)
        for lineno, line in enumerate(text.splitlines(), start=1)
        if lineno in lines
        for _ in pattern.finditer(line)
    ]


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
    if not isinstance(flags, list) or not all(isinstance(flag, str) for flag in flags):
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
