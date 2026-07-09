"""File and line counting metrics."""
from __future__ import annotations

from tingle.pacts.diff import DiffMetricContext, DiffResult, FileStatus
from tingle.pacts.metrics import MetricContext, MetricResult, Occurrence


def file_count(ctx: MetricContext) -> MetricResult:
    """Count the files selected by the metric's ranges."""
    return MetricResult(
        value=len(ctx.files),
        occurrences=tuple(Occurrence(path=str(path)) for path in ctx.files),
    )


def line_count(ctx: MetricContext) -> MetricResult:
    """Sum the line counts of every readable file."""
    total = 0
    details: dict[str, int] = {}
    warnings: list[str] = []
    for path in ctx.files:
        text = ctx.read(path)
        if text is None:
            warnings.append(f"{path}: skipped (binary, unreadable, or missing)")
            continue
        lines = len(text.splitlines())
        details[str(path)] = lines
        total += lines
    return MetricResult(value=total, details=details, warnings=tuple(warnings))


def file_count_diff(ctx: DiffMetricContext) -> DiffResult:
    """Files created by the branch vs files deleted."""
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


def line_count_diff(ctx: DiffMetricContext) -> DiffResult:
    """Lines added by the branch vs lines removed."""
    added = 0
    removed = 0
    details: dict[str, int] = {}
    for file in ctx.files:
        added += len(file.added_lines)
        removed += len(file.removed_lines)
        net = len(file.added_lines) - len(file.removed_lines)
        if net:
            details[str(file.path)] = net
    return DiffResult(
        net=added - removed, added=added, removed=removed, details=details
    )
