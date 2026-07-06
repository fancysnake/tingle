"""File and line counting metrics."""

from tingle.pacts.metrics import MetricContext, MetricResult


def file_count(ctx: MetricContext) -> MetricResult:
    """Count the files selected by the metric's ranges."""
    return MetricResult(value=len(ctx.files))


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
