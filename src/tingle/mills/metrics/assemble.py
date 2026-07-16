"""Shared plumbing for the built-in metrics.

Reading files and folding per-file findings into a result is the same
work for every metric that locates occurrences; only the per-file
analysis differs. These helpers own the sameness so each metric module
carries just its own analysis.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, TypeAlias

from tingle.pacts.diff import DiffResult
from tingle.pacts.metrics import MetricResult

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping
    from pathlib import PurePath

    from tingle.pacts.diff import FileDiff
    from tingle.pacts.metrics import MetricContext, Occurrence

#: What one file contributed to a diff: added, removed, and any warnings.
FileFindings: TypeAlias = "tuple[list[Occurrence], list[Occurrence], list[str]]"

#: One file's located hits, plus anything the analysis wants to warn about.
LocatedFinder: TypeAlias = (
    "Callable[[PurePath, str], tuple[list[Occurrence], list[str]]]"
)

#: The param every line-located metric reads to discard uninteresting hits.
IGNORE_LINES_PARAM = "ignore_lines"


def located_metric(
    ctx: MetricContext, *, find: LocatedFinder, suffix: str | None = None
) -> MetricResult:
    """Run a per-file finder over the context and fold its hits into a result.

    Every line-located metric does the same three things around its own
    analysis: read each file, drop the hits `ignore_lines` excuses, and
    count what is left. That sameness lives here, so `ignore_lines` works
    the same way in every metric that supports it -- and an ignored hit
    leaves no trace, neither in the value nor in the per-file details.
    """
    ignores = compile_ignores(ctx.params)
    details: dict[str, int] = {}
    warnings: list[str] = []
    occurrences: list[Occurrence] = []
    for path, text in readable_files(ctx, warnings, suffix=suffix):
        hits, found_warnings = find(path, text)
        warnings.extend(found_warnings)
        if found := drop_ignored(hits, text=text, patterns=ignores):
            details[str(path)] = len(found)
            occurrences.extend(found)
    return located_result(occurrences, details=details, warnings=warnings)


def compile_ignores(params: Mapping[str, Any]) -> tuple[re.Pattern[str], ...]:
    """Compile the metric's `ignore_lines` patterns; empty when it has none."""
    return tuple(
        re.compile(pattern) for pattern in params.get(IGNORE_LINES_PARAM, []) or []
    )


def validate_ignores(params: Mapping[str, Any]) -> list[str]:
    """Check that `ignore_lines` is a list of strings that compile."""
    if (patterns := params.get(IGNORE_LINES_PARAM)) is None:
        return []
    if not isinstance(patterns, list) or not all(
        isinstance(pattern, str) for pattern in patterns
    ):
        return ["ignore_lines must be a list of strings"]
    errors: list[str] = []
    for pattern in patterns:
        try:
            re.compile(pattern)
        except re.error as exc:
            errors.append(f"invalid ignore_lines pattern {pattern!r}: {exc}")
    return errors


def drop_ignored(
    occurrences: list[Occurrence], *, text: str, patterns: tuple[re.Pattern[str], ...]
) -> list[Occurrence]:
    r"""Drop the occurrences sitting on a line any pattern matches.

    A pattern is searched anywhere in the line, so `'"form":\s*ANY'`
    excuses `ANY` used as a placeholder without anchoring. A multi-line
    match is located at the line it starts on, so that first line is the
    only one tested.
    """
    if not patterns or not occurrences:
        return occurrences
    lines = text.splitlines()
    return [
        occurrence
        for occurrence in occurrences
        if not _is_ignored(occurrence, lines=lines, patterns=patterns)
    ]


def _is_ignored(
    occurrence: Occurrence, *, lines: list[str], patterns: tuple[re.Pattern[str], ...]
) -> bool:
    if occurrence.line is None or not 1 <= occurrence.line <= len(lines):
        return False
    line = lines[occurrence.line - 1]
    return any(pattern.search(line) for pattern in patterns)


def readable_files(
    ctx: MetricContext, warnings: list[str], *, suffix: str | None = None
) -> Iterator[tuple[PurePath, str]]:
    """Yield each readable file with its text, warning about the rest.

    `suffix` restricts the walk to one extension; those files are skipped
    silently, since a metric that only reads Python has nothing to say
    about a PNG.
    """
    for path in ctx.files:
        if suffix is not None and path.suffix != suffix:
            continue
        if (text := ctx.read(path)) is None:
            warnings.append(f"{path}: skipped (binary, unreadable, or missing)")
            continue
        yield path, text


def located_result(
    occurrences: list[Occurrence], *, details: dict[str, int], warnings: list[str]
) -> MetricResult:
    """Build the result of a metric whose value is its occurrence count."""
    return MetricResult(
        value=len(occurrences),
        details=details,
        warnings=tuple(warnings),
        occurrences=tuple(occurrences),
    )


def accumulate_diff(
    files: Iterable[FileDiff], per_file: Callable[[FileDiff], FileFindings]
) -> DiffResult:
    """Fold each file's findings into one diff result.

    Details carry the per-file net, and only for files the branch moved.
    """
    added: list[Occurrence] = []
    removed: list[Occurrence] = []
    details: dict[str, int] = {}
    warnings: list[str] = []

    for file in files:
        file_added, file_removed, file_warnings = per_file(file)
        added.extend(file_added)
        removed.extend(file_removed)
        warnings.extend(file_warnings)
        if net := len(file_added) - len(file_removed):
            details[str(file.path)] = net

    return DiffResult(
        net=len(added) - len(removed),
        added=len(added),
        removed=len(removed),
        details=details,
        warnings=tuple(warnings),
        added_occurrences=tuple(added),
        removed_occurrences=tuple(removed),
    )
