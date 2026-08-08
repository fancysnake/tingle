"""Shared plumbing for the built-in metrics.

Reading files and folding per-file findings into a result is the same
work for every metric that locates occurrences; only the per-file
analysis differs. These helpers own the sameness so each metric module
carries just its own analysis.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeAlias

from tingle.pacts.diff import DiffResult, FileStatus
from tingle.pacts.metrics import MetricResult, Occurrence

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping
    from pathlib import PurePath

    from tingle.pacts.diff import DiffMetricContext, FileDiff
    from tingle.pacts.metrics import MetricContext

#: What one file contributed to a diff: added, removed, and any warnings.
FileFindings: TypeAlias = "tuple[list[Occurrence], list[Occurrence], list[str]]"

#: One file's located hits, plus anything the analysis wants to warn about.
#: Warnings are bare messages: which file, and which side of a diff, they
#: concern is not the analysis's to know, and is prefixed on for it.
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
        warnings.extend(f"{path}: {warning}" for warning in found_warnings)
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


def excusing(
    find: LocatedFinder, patterns: tuple[re.Pattern[str], ...]
) -> LocatedFinder:
    """Wrap a finder so the hits `ignore_lines` excuses never surface.

    Every metric that excuses hits does it against the text the hits were
    found in, so the finder and its excuses travel together rather than as
    two things each caller has to remember to pair.
    """

    def find_kept(path: PurePath, text: str) -> tuple[list[Occurrence], list[str]]:
        hits, warnings = find(path, text)
        return drop_ignored(hits, text=text, patterns=patterns), warnings

    return find_kept


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


def per_file_result(located: MetricResult) -> MetricResult:
    """Collapse a located result so each file counts once, however many hits.

    The measure stops being volume and becomes spread: how far a thing has
    reached, not how heavily it is written where it already is. Reworking a
    file that already counted moves nothing; a fresh file that reaches for
    the thing is one more.

    Details are kept as they are -- the per-file hit count still says how
    heavily a file is involved -- so for a collapsed result the details sum
    to more than the value. Each file's occurrence is placed at its first
    hit, which is the useful line to open.
    """
    first: dict[str, int | None] = {}
    for occurrence in located.occurrences:
        first.setdefault(occurrence.path, occurrence.line)
    return MetricResult(
        value=len(first),
        details=located.details,
        warnings=located.warnings,
        occurrences=tuple(
            Occurrence(path=path, line=line) for path, line in first.items()
        ),
    )


def presence_crossings(
    ctx: DiffMetricContext, *, find: LocatedFinder, suffix: str | None = None
) -> DiffResult:
    """Count the files a thing appeared in, and the files it vanished from.

    What counts is *crossing*, not touching: a file holding the thing now
    but not at the base is spread taken on, one that held it then and does
    not now is spread contained. A file that held it before and holds it
    still counts for nothing however much of it the branch rewrote -- which
    is the point, since reworking legacy code is not spreading it.

    Both sides are read whole and re-analysed, with `ignore_lines` excusing
    hits on each side against its own text, exactly as a full run does; the
    touched line sets are never consulted. Only changed files are examined,
    which is sound: presence cannot flip in a file the branch left alone.

    A side that will not read counts as absent, and warns only when the
    file's status says it should have been there -- a deleted file has no
    current side, and that is not a problem worth a warning. A file neither
    side will read is a binary or a mode-only change: it holds the thing on
    neither side, which is unremarkable rather than worth warning twice.
    """
    kept = excusing(find, compile_ignores(ctx.params))

    def per_file(file: FileDiff) -> FileFindings:
        if suffix is not None and file.path.suffix != suffix:
            return [], [], []
        now_text, base_text = ctx.read(file.path), ctx.read_base(file.path)
        if now_text is None and base_text is None:
            return [], [], []
        now, warnings = _side_presence(now_text, file, find=kept, side=_CURRENT)
        before, base_warnings = _side_presence(base_text, file, find=kept, side=_BASE)
        warnings.extend(base_warnings)
        if now and not before:
            return [Occurrence(path=str(file.path))], [], warnings
        if before and not now:
            return [], [Occurrence(path=str(file.path))], warnings
        return [], [], warnings

    return accumulate_diff(ctx.files, per_file)


@dataclass(frozen=True)
class _Side:
    """One side of a diff: what to call it, and when it is meant to be empty."""

    label: str
    absent_status: FileStatus


_CURRENT = _Side("current", FileStatus.DELETED)
_BASE = _Side("base", FileStatus.ADDED)


def _side_presence(
    text: str | None, file: FileDiff, *, find: LocatedFinder, side: _Side
) -> tuple[bool, list[str]]:
    """Ask one side whether the thing is there; absent when it will not read."""
    if text is None:
        expected = file.status is not side.absent_status
        return False, [f"{file.path}: {side.label} side unreadable"] if expected else []
    hits, warnings = find(file.path, text)
    labelled = [f"{file.path}: {side.label} side: {warning}" for warning in warnings]
    return bool(hits), labelled


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
