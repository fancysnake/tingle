from __future__ import annotations

import json
from pathlib import Path

from tingle.gates.cli.render import report_table, run_json, run_listing
from tingle.mills.display import outcome_emoji, sections
from tingle.pacts.config import DEFAULT_GUIDE, MetricSpec
from tingle.pacts.metrics import MetricResult
from tingle.pacts.report import MetricOutcome, RunReport


def _outcome(name: str, group: str | None = None, *, value: int = 1) -> MetricOutcome:
    result = MetricResult(value=value)
    return MetricOutcome(
        spec=MetricSpec(name=name, type="file_count", group=group),
        range_names=(),
        emoji=outcome_emoji(result, DEFAULT_GUIDE),
        result=result,
    )


def _report(*outcomes: MetricOutcome) -> RunReport:
    return RunReport(
        root=Path("/proj"),
        source=Path("/proj/tingle.toml"),
        sections=sections(outcomes),
    )


def test_listing_has_group_headings() -> None:
    lines = run_listing(_report(_outcome("a", "typing"), _outcome("b")))
    text = "\n".join(line.plain for line in lines)

    assert "## typing" in text
    assert "## (ungrouped)" in text


def test_listing_without_groups_has_no_headings() -> None:
    lines = run_listing(_report(_outcome("a"), _outcome("b")))
    text = "\n".join(line.plain for line in lines)

    assert "##" not in text


def test_report_table_has_no_group_column_and_heads_groups_inline() -> None:
    """The outline drops the Group column: a group name heads its own row."""
    grouped = report_table(_report(_outcome("a", "typing"), _outcome("b")))
    plain = report_table(_report(_outcome("a"), _outcome("b")))

    assert "Group" not in [column.header for column in grouped.columns]
    assert "Group" not in [column.header for column in plain.columns]

    metric_cells = list(grouped.columns[0].cells)
    assert "[b]typing[/b]" in metric_cells  # the group heads its own row...
    assert "  a" in metric_cells  # ...with its metric indented beneath it
    assert "a" in list(plain.columns[0].cells)  # ungrouped: no indent


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
