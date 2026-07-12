"""Shared plumbing for the built-in metrics.

Reading files and folding per-file findings into a result is the same
work for every metric that locates occurrences; only the per-file
analysis differs. These helpers own the sameness so each metric module
carries just its own analysis.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

from tingle.pacts.diff import DiffResult
from tingle.pacts.metrics import MetricResult

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator
    from pathlib import PurePath

    from tingle.pacts.diff import FileDiff
    from tingle.pacts.metrics import MetricContext, Occurrence

#: What one file contributed to a diff: added, removed, and any warnings.
FileFindings: TypeAlias = "tuple[list[Occurrence], list[Occurrence], list[str]]"


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
