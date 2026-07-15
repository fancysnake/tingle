"""Rendering of run and diff reports: tables, listings, JSON, cobertura."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, TypeVar
from xml.etree import ElementTree as ET

from rich.table import Table
from rich.text import Text

from tingle.mills.display import group_summary, severity_emoji
from tingle.pacts.config import CheckPolicy

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tingle.pacts.check import CheckVerdict
    from tingle.pacts.diff import DiffOutcome, DiffReport, DiffResult
    from tingle.pacts.metrics import MetricResult, Occurrence
    from tingle.pacts.report import MetricOutcome, RunReport

_Outcome = TypeVar("_Outcome", bound="MetricOutcome | DiffOutcome")


def group_sections(
    outcomes: Sequence[_Outcome],
) -> list[tuple[str | None, list[_Outcome]]]:
    """Reshape outcomes into (group | None, outcomes) sections.

    Named groups come first in the order they first appear in config; the
    ungrouped (`None`) section is always last. Order within a section is
    preserved, so with no groups anywhere there is a single ungrouped
    section in the original order (byte-identical to pre-groups output).
    """
    sections: dict[str | None, list[_Outcome]] = {}
    for outcome in outcomes:
        sections.setdefault(outcome.spec.group, []).append(outcome)
    ungrouped = sections.pop(None, None)
    result: list[tuple[str | None, list[_Outcome]]] = list(sections.items())
    if ungrouped is not None:
        result.append((None, ungrouped))
    return result


def _in_section_order(outcomes: Sequence[_Outcome]) -> list[_Outcome]:
    """Flatten outcomes into group_sections order (ungrouped last)."""
    return [outcome for _name, group in group_sections(outcomes) for outcome in group]


def _section_heading(
    name: str | None, outcomes: Sequence[_Outcome], *, has_named: bool
) -> Text | None:
    """Bold heading for a section, or None to preserve headingless output.

    The sole ungrouped section, when no named group exists, keeps today's
    heading-free output and returns None.
    """
    if name is None and not has_named:
        return None
    summary = group_summary(outcomes)
    stat = _valued(summary.value, summary.guide)
    return Text(f"## {_group_label(name)}  {stat}", style="bold")


def _description_line(outcome: _Outcome) -> Text | None:
    """Return the metric's own words about what it measures, if it has any."""
    if (description := outcome.spec.description) is None:
        return None
    return Text(f"  {description}", style="dim italic")


def report_table(report: RunReport) -> Table:
    """Compact summary table of a full run.

    Grouped, it reads as an outline: each group name heads its own metric
    rows, indented under it, with the group's summed value on the heading
    line. No separate Group column, so a heading is never mistaken for a
    nameless metric that somehow carries a value.
    """
    sections = group_sections(report.outcomes)
    grouped = any(name is not None for name, _ in sections)
    numbers = [
        outcome.result.value
        for _name, outcomes in sections
        for outcome in outcomes
        if outcome.result is not None
    ]
    if grouped:
        numbers += [group_summary(outcomes).value for _name, outcomes in sections]
    width = _value_width(numbers)
    table = Table(title=str(report.root))
    table.add_column("Metric")
    table.add_column("Type")
    table.add_column("Ranges")
    table.add_column("Value", justify="right")
    for index, (name, outcomes) in enumerate(sections):
        if index > 0:
            table.add_section()
        if grouped:
            summary = group_summary(outcomes)
            table.add_row(
                f"[b]{_group_label(name)}[/b]",
                "",
                "",
                f"[b]{_valued(summary.value, summary.guide, width=width)}[/b]",
            )
        for outcome in outcomes:
            value = (
                "[red]ERROR[/]"
                if outcome.result is None
                else _valued(outcome.result.value, outcome.guide, width=width)
            )
            table.add_row(
                _metric_label(outcome.spec.name, grouped=grouped),
                outcome.spec.type,
                ", ".join(outcome.range_names),
                value,
            )
    return table


def _valued(value: int, guide: int, *, width: int = 0) -> str:
    """Render a measured number, led by how bad it is against its guide.

    `width` right-pads the number with spaces so that, down a column, every
    emoji lands in the same place and the digits line up under each other.
    """
    return f"{severity_emoji(value, guide)} {value:>{width}}"


def _metric_label(name: str, *, grouped: bool) -> str:
    """Indent a metric name under its group heading, when there are groups."""
    return f"  {name}" if grouped else name


def _value_width(numbers: Sequence[int]) -> int:
    """Widest rendered number, so the emoji column can be aligned to it.

    Only the numbers that will actually show are passed in; errored metrics
    render no number and so are left out.
    """
    return max((len(str(number)) for number in numbers), default=1)


def _group_label(name: str | None) -> str:
    return name if name is not None else "(ungrouped)"


def diff_table(report: DiffReport) -> Table:
    """Compact summary table of a branch diff.

    Grouped, it reads as an outline like `report_table`: the group name heads
    its indented metric rows, carrying the group's net beside its standing
    total. No separate Group column.
    """
    sections = group_sections(report.outcomes)
    grouped = any(name is not None for name, _ in sections)
    numbers = [
        outcome.total.value
        for _name, outcomes in sections
        for outcome in outcomes
        if outcome.total is not None
    ]
    if grouped:
        numbers += [group_summary(outcomes).value for _name, outcomes in sections]
    width = _value_width(numbers)
    table = Table(title=f"{report.root} vs {report.base_ref}")
    table.add_column("Metric")
    table.add_column("Type")
    table.add_column("Added", justify="right")
    table.add_column("Removed", justify="right")
    table.add_column("Net", justify="right")
    table.add_column("Total", justify="right")
    for index, (name, outcomes) in enumerate(sections):
        if index > 0:
            table.add_section()
        if grouped:
            summary = group_summary(outcomes)
            table.add_row(
                f"[b]{_group_label(name)}[/b]",
                "",
                "",
                "",
                _net_cell(summary.net or 0),
                # the standing debt, not the net: a net of zero is not no debt
                f"[b]{_valued(summary.value, summary.guide, width=width)}[/b]",
            )
        for outcome in outcomes:
            table.add_row(
                _metric_label(outcome.spec.name, grouped=grouped),
                outcome.spec.type,
                *_diff_cells(outcome, width),
            )
    return table


def _diff_cells(outcome: DiffOutcome, width: int) -> tuple[str, str, str, str]:
    """Render the added/removed/net/total cells of one diff row."""
    if outcome.result is None:
        return ("", "", "[red]ERROR[/]", "")
    return (
        _added_cell(outcome.result.added),
        _removed_cell(outcome.result.removed),
        _net_cell(outcome.result.net),
        (
            _valued(outcome.total.value, outcome.guide, width=width)
            if outcome.total
            else ""
        ),
    )


def run_listing(report: RunReport) -> list[Text]:
    """Full report: every metric with its located occurrences."""
    lines: list[Text] = []
    sections = group_sections(report.outcomes)
    has_named = any(name is not None for name, _ in sections)
    for name, outcomes in sections:
        if (
            heading := _section_heading(name, outcomes, has_named=has_named)
        ) is not None:
            lines.append(heading)
        for outcome in outcomes:
            if outcome.result is None:
                lines.append(
                    Text(
                        f"{outcome.spec.name} ({outcome.spec.type}): ERROR",
                        style="bold red",
                    )
                )
                lines.append(Text(""))
                continue
            stat = _valued(outcome.result.value, outcome.guide)
            lines.append(
                Text(f"{outcome.spec.name} ({outcome.spec.type}): {stat}", style="bold")
            )
            if (description := _description_line(outcome)) is not None:
                lines.append(description)
            lines.extend(occurrence_lines(outcome.result))
            lines.append(Text(""))
    return lines


def occurrence_rows(result: MetricResult) -> list[tuple[Text, Occurrence | None]]:
    """Occurrence lines paired with the hit each renders (None for a placeholder).

    The pairing lets a caller that wants to act on a line -- the TUI opening
    it in an editor -- reach the hit's path and line without parsing the text.
    """
    if result.occurrences:
        return [
            (Text(f"  {occurrence}"), occurrence) for occurrence in result.occurrences
        ]
    return [(Text("  (no located occurrences)", style="dim"), None)]


def occurrence_lines(result: MetricResult) -> list[Text]:
    """Indented occurrence lines of one metric result."""
    return [text for text, _occurrence in occurrence_rows(result)]


def diff_occurrence_rows(result: DiffResult) -> list[tuple[Text, Occurrence | None]]:
    """Signed occurrence lines, each paired with its hit (None for a placeholder)."""
    if not result.added_occurrences and not result.removed_occurrences:
        return [(Text("  (no located changes)", style="dim"), None)]
    rows: list[tuple[Text, Occurrence | None]] = [
        (Text(f"  + {occurrence}", style="red"), occurrence)
        for occurrence in result.added_occurrences
    ]
    rows += [
        (Text(f"  - {occurrence}", style="green"), occurrence)
        for occurrence in result.removed_occurrences
    ]
    return rows


def diff_occurrence_lines(result: DiffResult) -> list[Text]:
    """Signed, colored occurrence lines of one diff result."""
    return [text for text, _occurrence in diff_occurrence_rows(result)]


def diff_listing(report: DiffReport) -> list[Text]:
    """Full diff report: added/removed occurrences per metric."""
    lines: list[Text] = []
    sections = group_sections(report.outcomes)
    has_named = any(name is not None for name, _ in sections)
    for name, outcomes in sections:
        if (
            heading := _section_heading(name, outcomes, has_named=has_named)
        ) is not None:
            lines.append(heading)
        for outcome in outcomes:
            if outcome.result is None:
                lines.append(
                    Text(
                        f"{outcome.spec.name} ({outcome.spec.type}): ERROR",
                        style="bold red",
                    )
                )
                lines.append(Text(""))
                continue
            lines.append(_diff_heading(outcome))
            if (description := _description_line(outcome)) is not None:
                lines.append(description)
            lines.extend(diff_occurrence_lines(outcome.result))
            lines.append(Text(""))
    return lines


def _diff_heading(outcome: DiffOutcome) -> Text:
    if (result := outcome.result) is None:  # pragma: no cover - guarded by caller
        return Text("")
    impact = (
        f"+{result.added} / -{result.removed} (net {result.net:+d})"
        if result.added is not None and result.removed is not None
        else f"net {result.net:+d}"
    )
    return Text(f"{outcome.spec.name} ({outcome.spec.type}): {impact}", style="bold")


def check_listing(verdict: CheckVerdict) -> list[Text]:
    """List the worsened metrics and, under each, only what the branch added.

    Nothing else: no removed occurrences, no unchanged metrics, no
    summary table. What a CI log should show is the debt to answer for.
    """
    lines: list[Text] = []
    for outcome in verdict.worsened:
        if (result := outcome.result) is None:  # pragma: no cover - never worsened
            continue
        lines.append(
            Text(
                f"{outcome.spec.name} ({outcome.spec.type}): +{result.net}",
                style="bold red",
            )
        )
        lines.extend(
            Text(f"  + {occurrence}", style="red")
            for occurrence in result.added_occurrences
        )
        if not result.added_occurrences:
            lines.append(Text("  (no located additions)", style="dim"))
        lines.append(Text(""))
    return lines


def check_success(verdict: CheckVerdict, base: str) -> Text:
    """Say the branch passed, so a green CI log cannot read as a step that never ran.

    The mirror of `check_reason`, which explains the failing side. A passing
    check printed nothing at all before, which is indistinguishable from
    tingle not having run.
    """
    metrics = "metric" if verdict.judged == 1 else "metrics"
    against = f"{verdict.judged} {metrics} against {base}"
    if verdict.net_total < 0:
        paid = -verdict.net_total
        return Text(f"🎉 no new debt, and {paid} paid off: {against}", style="green")
    return Text(f"🎉 no new debt: {against}", style="green")


def check_reason(verdict: CheckVerdict) -> str:
    """One line saying which policy failed the branch, and by how much."""
    if verdict.policy is CheckPolicy.SUM:
        return f"check failed: metrics grew by a net +{verdict.net_total} (policy: sum)"
    grown = ", ".join(outcome.spec.name for outcome in verdict.worsened)
    return f"check failed: {grown} grew (policy: any)"


def stat_json(report: RunReport) -> str:
    """Machine-readable run summary: values only, as the stat table."""
    return _run_json(report, detailed=False)


def run_json(report: RunReport) -> str:
    """Machine-readable full run, occurrences and details included."""
    return _run_json(report, detailed=True)


def stat_diff_json(report: DiffReport) -> str:
    """Machine-readable branch diff summary: values only."""
    return _diff_json(report, detailed=False)


def diff_json(report: DiffReport) -> str:
    """Machine-readable branch diff, occurrences and details included."""
    return _diff_json(report, detailed=True)


def _run_json(report: RunReport, *, detailed: bool) -> str:
    return json.dumps(
        {
            "root": str(report.root),
            "config": str(report.source),
            "metrics": [
                {
                    "name": outcome.spec.name,
                    "type": outcome.spec.type,
                    "group": outcome.spec.group,
                    "description": outcome.spec.description,
                    "guide": outcome.guide,
                    "ranges": list(outcome.range_names),
                    "value": outcome.result.value if outcome.result else None,
                    **(_run_details(outcome) if detailed else {}),
                    "warnings": list(outcome.result.warnings) if outcome.result else [],
                    "error": outcome.error,
                }
                for outcome in _in_section_order(report.outcomes)
            ],
        },
        indent=2,
    )


def _diff_json(report: DiffReport, *, detailed: bool) -> str:
    return json.dumps(
        {
            "root": str(report.root),
            "config": str(report.source),
            "base": report.base_ref,
            "merge_base": report.merge_base,
            "metrics": [
                {
                    "name": outcome.spec.name,
                    "type": outcome.spec.type,
                    "group": outcome.spec.group,
                    "description": outcome.spec.description,
                    "guide": outcome.guide,
                    "ranges": list(outcome.range_names),
                    **_diff_values(outcome),
                    **(_diff_details(outcome) if detailed else {}),
                    "total": outcome.total.value if outcome.total else None,
                    "warnings": list(outcome.result.warnings) if outcome.result else [],
                    "error": outcome.error,
                }
                for outcome in _in_section_order(report.outcomes)
            ],
            "skipped": list(report.skipped),
        },
        indent=2,
    )


def _run_details(outcome: MetricOutcome) -> dict[str, Any]:
    result = outcome.result
    return {
        "details": dict(result.details) if result else {},
        "occurrences": _occurrences_json(result.occurrences if result else ()),
    }


def _diff_values(outcome: DiffOutcome) -> dict[str, Any]:
    if (result := outcome.result) is None:
        return {"added": None, "removed": None, "net": None}
    return {"added": result.added, "removed": result.removed, "net": result.net}


def _diff_details(outcome: DiffOutcome) -> dict[str, Any]:
    if (result := outcome.result) is None:
        return {"details": {}, "added_occurrences": [], "removed_occurrences": []}
    return {
        "details": dict(result.details),
        "added_occurrences": _occurrences_json(result.added_occurrences),
        "removed_occurrences": _occurrences_json(result.removed_occurrences),
    }


def cobertura(report: RunReport) -> tuple[str, list[str]]:
    """Cobertura XML where every located occurrence is an uncovered line.

    The format is line-based, so only metrics with line-located
    occurrences contribute; the second return value names the excluded
    metrics.

    Consumers (GitLab MR widgets, Jenkins, diff-cover) then annotate the
    occurrence lines as "uncovered", i.e. carrying debt.
    """
    excluded: list[str] = []
    packages = ET.Element("packages")
    total_lines = 0
    for outcome in report.outcomes:
        if outcome.result is None:
            continue
        if not (
            located := [o for o in outcome.result.occurrences if o.line is not None]
        ):
            if outcome.result.occurrences or outcome.result.value:
                excluded.append(outcome.spec.name)
            continue
        total_lines += _cobertura_package(packages, outcome.spec.name, located=located)

    root = ET.Element(
        "coverage",
        {
            "version": "tingle",
            "timestamp": "0",
            "lines-valid": str(total_lines),
            "lines-covered": "0",
            "line-rate": "0",
        },
    )
    sources = ET.SubElement(root, "sources")
    ET.SubElement(sources, "source").text = str(report.root)
    root.append(packages)
    xml = ET.tostring(root, encoding="unicode", xml_declaration=True)
    return xml, excluded


def _cobertura_package(
    packages: ET.Element, name: str, *, located: list[Occurrence]
) -> int:
    package = ET.SubElement(packages, "package", {"name": name, "line-rate": "0"})
    classes = ET.SubElement(package, "classes")
    by_file: dict[str, set[int]] = {}
    for occurrence in located:
        if occurrence.line is not None:
            by_file.setdefault(occurrence.path, set()).add(occurrence.line)
    total = 0
    for path in sorted(by_file):
        cls = ET.SubElement(
            classes, "class", {"name": path, "filename": path, "line-rate": "0"}
        )
        ET.SubElement(cls, "methods")
        lines = ET.SubElement(cls, "lines")
        for line in sorted(by_file[path]):
            ET.SubElement(lines, "line", {"number": str(line), "hits": "0"})
        total += len(by_file[path])
    return total


def _occurrences_json(occurrences: tuple[Occurrence, ...]) -> list[dict[str, Any]]:
    return [
        {"file": occurrence.path, "line": occurrence.line, "note": occurrence.note}
        for occurrence in occurrences
    ]


def _added_cell(added: int | None) -> str:
    if added is None:
        return ""
    return f"[red]+{added}[/]" if added > 0 else "0"


def _removed_cell(removed: int | None) -> str:
    if removed is None:
        return ""
    return f"[green]-{removed}[/]" if removed > 0 else "0"


def _net_cell(net: int) -> str:
    if net > 0:
        return f"[red]+{net}[/]"
    if net < 0:
        return f"[green]{net}[/]"
    return "0"
