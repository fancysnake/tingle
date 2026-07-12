"""Regex match counting metric."""

from __future__ import annotations

import re
from bisect import bisect_right
from typing import TYPE_CHECKING, Any

from tingle.mills.metrics.assemble import (
    FileFindings,
    accumulate_diff,
    compile_ignores,
    drop_ignored,
    located_metric,
    validate_ignores,
)
from tingle.pacts.metrics import MetricContext, MetricResult, Occurrence

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from collections.abc import Set as AbstractSet
    from pathlib import PurePath

    from tingle.pacts.diff import DiffMetricContext, DiffResult, FileDiff

_FLAGS = {"IGNORECASE": re.IGNORECASE, "MULTILINE": re.MULTILINE, "DOTALL": re.DOTALL}


def regex_count(ctx: MetricContext) -> MetricResult:
    """Count matches of the `pattern` param across the context's files.

    Matching is full-text (multi-line patterns work); each match is
    located at the line where it starts.
    """
    pattern = _compile(ctx.params)

    def find(path: PurePath, text: str) -> tuple[list[Occurrence], list[str]]:
        line_starts = _line_starts(text)
        return [
            Occurrence(path=str(path), line=bisect_right(line_starts, match.start()))
            for match in pattern.finditer(text)
        ], []

    return located_metric(ctx, find=find)


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
    ignores = compile_ignores(ctx.params)

    def per_file(file: FileDiff) -> FileFindings:
        warnings: list[str] = []
        added = _matches_on_lines(
            pattern, ctx.read, file=file, lines=file.added_lines, ignores=ignores
        )
        removed = _matches_on_lines(
            pattern, ctx.read_base, file=file, lines=file.removed_lines, ignores=ignores
        )
        if added is None:
            warnings.append(f"{file.path}: current side unreadable")
            added = []
        if removed is None:
            warnings.append(f"{file.path}: base side unreadable")
            removed = []
        return added, removed, warnings

    return accumulate_diff(ctx.files, per_file)


def _matches_on_lines(
    pattern: re.Pattern[str],
    reader: Callable[..., str | None],
    *,
    file: FileDiff,
    lines: AbstractSet[int],
    ignores: tuple[re.Pattern[str], ...],
) -> list[Occurrence] | None:
    """Locate matches on the given line numbers; None when text is unreadable.

    Each side is filtered against its own text, so a line the metric
    ignores on the branch is equally ignored in the base and the net
    stays honest.
    """
    if not lines:
        return []
    if (text := reader(file.path)) is None:
        return None
    return drop_ignored(
        [
            Occurrence(path=str(file.path), line=lineno)
            for lineno, line in enumerate(text.splitlines(), start=1)
            if lineno in lines
            for _ in pattern.finditer(line)
        ],
        text=text,
        patterns=ignores,
    )


def validate_params(params: Mapping[str, Any]) -> list[str]:
    """Check that `pattern` compiles, `flags` are known, and ignores compile."""
    errors: list[str] = validate_ignores(params)

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
