from __future__ import annotations

import json
from pathlib import Path

from tingle.gates.cli.render import group_sections, report_table, run_json, run_listing
from tingle.pacts.config import MetricSpec
from tingle.pacts.metrics import MetricResult
from tingle.pacts.report import MetricOutcome, RunReport


def _outcome(name: str, group: str | None = None, *, value: int = 1) -> MetricOutcome:
    return MetricOutcome(
        spec=MetricSpec(name=name, type="file_count", group=group),
        range_names=(),
        result=MetricResult(value=value),
    )


def _report(*outcomes: MetricOutcome) -> RunReport:
    return RunReport(
        root=Path("/proj"), source=Path("/proj/tingle.toml"), outcomes=outcomes
    )


def test_group_sections_first_appearance_order_ungrouped_last() -> None:
    sections = group_sections(
        (
            _outcome("a", "typing"),
            _outcome("b", "lint"),
            _outcome("c", "typing"),  # scattered member of an earlier group
            _outcome("d"),  # ungrouped
        )
    )

    names = [(group, [o.spec.name for o in outs]) for group, outs in sections]
    assert names == [("typing", ["a", "c"]), ("lint", ["b"]), (None, ["d"])]


def test_group_sections_no_groups_single_section_original_order() -> None:
    sections = group_sections((_outcome("a"), _outcome("b")))

    assert len(sections) == 1
    group, outs = sections[0]
    assert group is None
    assert [o.spec.name for o in outs] == ["a", "b"]


def test_listing_has_group_headings() -> None:
    lines = run_listing(_report(_outcome("a", "typing"), _outcome("b")))
    text = "\n".join(line.plain for line in lines)

    assert "## typing" in text
    assert "## (ungrouped)" in text


def test_listing_without_groups_has_no_headings() -> None:
    lines = run_listing(_report(_outcome("a"), _outcome("b")))
    text = "\n".join(line.plain for line in lines)

    assert "##" not in text


def test_report_table_group_column_only_when_grouped() -> None:
    grouped = report_table(_report(_outcome("a", "typing"), _outcome("b")))
    plain = report_table(_report(_outcome("a"), _outcome("b")))

    assert next(column.header for column in grouped.columns) == "Group"
    assert "Group" not in [column.header for column in plain.columns]


def test_json_carries_group_and_null_when_unset() -> None:
    payload = json.loads(run_json(_report(_outcome("a", "typing"), _outcome("b"))))
    by_name = {entry["name"]: entry for entry in payload["metrics"]}

    assert by_name["a"]["group"] == "typing"
    assert by_name["b"]["group"] is None


def test_json_follows_section_order() -> None:
    payload = json.loads(
        run_json(
            _report(
                _outcome("a", "typing"),
                _outcome("b"),  # ungrouped, defined before c
                _outcome("c", "typing"),
            )
        )
    )

    # ungrouped 'b' sinks below the typing section despite config order
    assert [entry["name"] for entry in payload["metrics"]] == ["a", "c", "b"]
