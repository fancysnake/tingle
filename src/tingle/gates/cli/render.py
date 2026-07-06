"""Rendering of run and diff reports: tables, listings, JSON, cobertura."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET

from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from tingle.pacts.diff import DiffOutcome, DiffReport
    from tingle.pacts.metrics import Occurrence
    from tingle.pacts.report import RunReport


def report_table(report: RunReport) -> Table:
    """Compact summary table of a full run."""
    table = Table(title=str(report.root))
    table.add_column("Metric")
    table.add_column("Type")
    table.add_column("Ranges")
    table.add_column("Value", justify="right")
    for outcome in report.outcomes:
        value = (
            "[red]ERROR[/]"
            if outcome.result is None
            else str(outcome.result.value)
        )
        table.add_row(
            outcome.spec.name,
            outcome.spec.type,
            ", ".join(outcome.range_names),
            value,
        )
    return table


def diff_table(report: DiffReport) -> Table:
    """Compact summary table of a branch diff."""
    table = Table(title=f"{report.root} vs {report.base_ref}")
    table.add_column("Metric")
    table.add_column("Type")
    table.add_column("Added", justify="right")
    table.add_column("Removed", justify="right")
    table.add_column("Net", justify="right")
    table.add_column("Total", justify="right")
    for outcome in report.outcomes:
        if outcome.result is None:
            cells = ("", "", "[red]ERROR[/]", "")
        else:
            cells = (
                _added_cell(outcome.result.added),
                _removed_cell(outcome.result.removed),
                _net_cell(outcome.result.net),
                str(outcome.total.value) if outcome.total else "",
            )
        table.add_row(outcome.spec.name, outcome.spec.type, *cells)
    return table


def run_listing(report: RunReport) -> list[Text]:
    """Full report: every metric with its located occurrences."""
    lines: list[Text] = []
    for outcome in report.outcomes:
        if outcome.result is None:
            lines.append(
                Text(
                    f"{outcome.spec.name} ({outcome.spec.type}): ERROR",
                    style="bold red",
                )
            )
            lines.append(Text(""))
            continue
        lines.append(
            Text(
                f"{outcome.spec.name} ({outcome.spec.type}): "
                f"{outcome.result.value}",
                style="bold",
            )
        )
        if outcome.result.occurrences:
            lines.extend(
                Text(f"  {occurrence}")
                for occurrence in outcome.result.occurrences
            )
        else:
            lines.append(Text("  (no located occurrences)", style="dim"))
        lines.append(Text(""))
    return lines


def diff_listing(report: DiffReport) -> list[Text]:
    """Full diff report: added/removed occurrences per metric."""
    lines: list[Text] = []
    for outcome in report.outcomes:
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
        result = outcome.result
        if not result.added_occurrences and not result.removed_occurrences:
            lines.append(Text("  (no located changes)", style="dim"))
        lines.extend(
            Text(f"  + {occurrence}", style="red")
            for occurrence in result.added_occurrences
        )
        lines.extend(
            Text(f"  - {occurrence}", style="green")
            for occurrence in result.removed_occurrences
        )
        lines.append(Text(""))
    return lines


def _diff_heading(outcome: DiffOutcome) -> Text:
    result = outcome.result
    if result is None:  # pragma: no cover - guarded by caller
        return Text("")
    if result.added is not None and result.removed is not None:
        impact = f"+{result.added} / -{result.removed} (net {result.net:+d})"
    else:
        impact = f"net {result.net:+d}"
    return Text(
        f"{outcome.spec.name} ({outcome.spec.type}): {impact}", style="bold"
    )


def run_json(report: RunReport) -> str:
    """Machine-readable full run, occurrences included."""
    return json.dumps(
        {
            "root": str(report.root),
            "config": str(report.source),
            "metrics": [
                {
                    "name": outcome.spec.name,
                    "type": outcome.spec.type,
                    "ranges": list(outcome.range_names),
                    "value": outcome.result.value if outcome.result else None,
                    "details": dict(outcome.result.details)
                    if outcome.result
                    else {},
                    "occurrences": _occurrences_json(
                        outcome.result.occurrences if outcome.result else ()
                    ),
                    "warnings": (
                        list(outcome.result.warnings) if outcome.result else []
                    ),
                    "error": outcome.error,
                }
                for outcome in report.outcomes
            ],
        },
        indent=2,
    )


def diff_json(report: DiffReport) -> str:
    """Machine-readable branch diff, occurrences included."""
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
                    "ranges": list(outcome.range_names),
                    **_diff_values(outcome),
                    "total": outcome.total.value if outcome.total else None,
                    "warnings": (
                        list(outcome.result.warnings) if outcome.result else []
                    ),
                    "error": outcome.error,
                }
                for outcome in report.outcomes
            ],
            "skipped": list(report.skipped),
        },
        indent=2,
    )


def _diff_values(outcome: DiffOutcome) -> dict[str, Any]:
    result = outcome.result
    if result is None:
        return {
            "added": None,
            "removed": None,
            "net": None,
            "details": {},
            "added_occurrences": [],
            "removed_occurrences": [],
        }
    return {
        "added": result.added,
        "removed": result.removed,
        "net": result.net,
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
        located = [o for o in outcome.result.occurrences if o.line is not None]
        if not located:
            if outcome.result.occurrences or outcome.result.value:
                excluded.append(outcome.spec.name)
            continue
        total_lines += _cobertura_package(packages, outcome.spec.name, located)

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
    packages: ET.Element, name: str, located: list[Occurrence]
) -> int:
    package = ET.SubElement(
        packages, "package", {"name": name, "line-rate": "0"}
    )
    classes = ET.SubElement(package, "classes")
    by_file: dict[str, set[int]] = {}
    for occurrence in located:
        if occurrence.line is not None:
            by_file.setdefault(occurrence.path, set()).add(occurrence.line)
    total = 0
    for path in sorted(by_file):
        cls = ET.SubElement(
            classes,
            "class",
            {"name": path, "filename": path, "line-rate": "0"},
        )
        ET.SubElement(cls, "methods")
        lines = ET.SubElement(cls, "lines")
        for line in sorted(by_file[path]):
            ET.SubElement(
                lines, "line", {"number": str(line), "hits": "0"}
            )
        total += len(by_file[path])
    return total


def _occurrences_json(
    occurrences: tuple[Occurrence, ...],
) -> list[dict[str, Any]]:
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
