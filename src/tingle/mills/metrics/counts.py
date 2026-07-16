"""File and line counting metrics."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tingle.mills.metrics.assemble import (
    FileFindings,
    accumulate_diff,
    located_result,
    readable_files,
)
from tingle.pacts.diff import DiffMetricContext, DiffResult, FileStatus
from tingle.pacts.metrics import MetricContext, MetricResult, Occurrence

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import PurePath

    from tingle.pacts.diff import FileDiff

#: Gate param: count only files strictly longer than this many lines.
OVER_LINES_PARAM = "over_lines"


def file_count(ctx: MetricContext) -> MetricResult:
    """Count the files selected by the metric's ranges.

    With `over_lines`, only the files strictly longer than the gate count,
    and each one's length lands in `details` -- so the report says not just
    which files are oversized, but by how much. Without it no file is
    opened at all, which is what keeps a plain `file_count` free of the
    unreadable-file warnings a read would produce.
    """
    if (gate := _gate(ctx.params)) is None:
        return MetricResult(
            value=len(ctx.files),
            occurrences=tuple(Occurrence(path=str(path)) for path in ctx.files),
        )

    details: dict[str, int] = {}
    warnings: list[str] = []
    occurrences: list[Occurrence] = []
    for path, text in readable_files(ctx, warnings):
        if (lines := _line_count(text)) > gate:
            # the length, not a count: the report says by how much it is over
            details[str(path)] = lines
            occurrences.append(Occurrence(path=str(path), note=f"{lines} lines"))
    return located_result(occurrences, details=details, warnings=warnings)


def line_count(ctx: MetricContext) -> MetricResult:
    """Sum the line counts of every readable file."""
    total = 0
    details: dict[str, int] = {}
    warnings: list[str] = []
    for path, text in readable_files(ctx, warnings):
        lines = _line_count(text)
        details[str(path)] = lines
        total += lines
    return MetricResult(value=total, details=details, warnings=tuple(warnings))


def file_count_diff(ctx: DiffMetricContext) -> DiffResult:
    """Files created by the branch vs files deleted.

    With `over_lines`, what counts is not creation but *crossing*: a file
    that grew past the gate is new debt though it already existed, and one
    refactored back under it is debt paid off. Deletion and creation fall
    out of the same comparison -- a deleted file has no current side and so
    is never over the gate, a created file has no base side.
    """
    if (gate := _gate(ctx.params)) is not None:
        return _crossings(ctx, gate=gate)

    created = tuple(
        Occurrence(path=str(file.path))
        for file in ctx.files
        if file.status is FileStatus.ADDED
    )
    deleted = tuple(
        Occurrence(path=str(file.path))
        for file in ctx.files
        if file.status is FileStatus.DELETED
    )
    return DiffResult(
        net=len(created) - len(deleted),
        added=len(created),
        removed=len(deleted),
        added_occurrences=created,
        removed_occurrences=deleted,
    )


def _crossings(ctx: DiffMetricContext, *, gate: int) -> DiffResult:
    """Count the files the branch pushed over the gate, and pulled back under."""

    def per_file(file: FileDiff) -> FileFindings:
        now = _side_lines(ctx.read, file.path)
        before = _side_lines(ctx.read_base, file.path)
        is_over = now is not None and now > gate
        was_over = before is not None and before > gate
        if is_over and not was_over:
            return [Occurrence(path=str(file.path), note=f"{now} lines")], [], []
        if was_over and not is_over:
            return [], [Occurrence(path=str(file.path), note=f"was {before} lines")], []
        return [], [], []

    return accumulate_diff(ctx.files, per_file)


def _side_lines(reader: Callable[[PurePath], str | None], path: PurePath) -> int | None:
    """Line count of one side, or None when the file is not there to read."""
    if (text := reader(path)) is None:
        return None
    return _line_count(text)


def _line_count(text: str) -> int:
    return len(text.splitlines())


def _gate(params: Mapping[str, Any]) -> int | None:
    """Return the `over_lines` gate, or None when the metric sets none."""
    gate = params.get(OVER_LINES_PARAM)
    return gate if isinstance(gate, int) else None


def validate_count_params(params: Mapping[str, Any]) -> list[str]:
    """Check that `over_lines`, when given, is a positive integer."""
    if (gate := params.get(OVER_LINES_PARAM)) is None:
        return []
    if isinstance(gate, bool) or not isinstance(gate, int) or gate <= 0:
        return ["over_lines must be a positive integer"]
    return []


def line_count_diff(ctx: DiffMetricContext) -> DiffResult:
    """Lines added by the branch vs lines removed."""
    added = 0
    removed = 0
    details: dict[str, int] = {}
    for file in ctx.files:
        added += len(file.added_lines)
        removed += len(file.removed_lines)
        if net := len(file.added_lines) - len(file.removed_lines):
            details[str(file.path)] = net
    return DiffResult(
        net=added - removed, added=added, removed=removed, details=details
    )
