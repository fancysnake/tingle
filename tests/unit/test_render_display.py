from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

from tingle.gates.cli.render import (
    check_success,
    diff_json,
    diff_listing,
    diff_table,
    report_table,
    run_json,
    run_listing,
)
from tingle.pacts.check import CheckVerdict
from tingle.pacts.config import CheckPolicy, MetricSpec
from tingle.pacts.diff import DiffOutcome, DiffReport, DiffResult
from tingle.pacts.metrics import MetricResult
from tingle.pacts.report import MetricOutcome, RunReport

if TYPE_CHECKING:
    from rich.text import Text


def _outcome(
    name: str,
    group: str | None = None,
    *,
    value: int = 1,
    guide: int = 100,
    description: str | None = None,
) -> MetricOutcome:
    return MetricOutcome(
        spec=MetricSpec(
            name=name, type="file_count", group=group, description=description
        ),
        range_names=(),
        result=MetricResult(value=value),
        guide=guide,
    )


def _failed(name: str, group: str | None = None) -> MetricOutcome:
    return MetricOutcome(
        spec=MetricSpec(name=name, type="file_count", group=group),
        range_names=(),
        error="ValueError: boom",
    )


def _report(*outcomes: MetricOutcome) -> RunReport:
    return RunReport(
        root=Path("/proj"), source=Path("/proj/tingle.toml"), outcomes=outcomes
    )


def _diff_outcome(
    name: str,
    group: str | None = None,
    *,
    net: int = 0,
    total: int = 0,
    guide: int = 100,
) -> DiffOutcome:
    return DiffOutcome(
        spec=MetricSpec(name=name, type="file_count", group=group),
        range_names=(),
        result=DiffResult(net=net, added=max(net, 0), removed=max(-net, 0)),
        total=MetricResult(value=total),
        guide=guide,
    )


def _diff_report(*outcomes: DiffOutcome) -> DiffReport:
    return DiffReport(
        root=Path("/proj"),
        source=Path("/proj/tingle.toml"),
        base_ref="main",
        merge_base="abc123",
        outcomes=outcomes,
    )


def _rendered(renderable: object) -> str:
    console = Console(width=200, record=True, no_color=True)
    console.print(renderable)
    return console.export_text()


def _plain(lines: list[Text]) -> str:
    return "\n".join(line.plain for line in lines)


def test_table_values_carry_their_severity_emoji() -> None:
    text = _rendered(report_table(_report(_outcome("a", value=0, guide=100))))

    assert "🎉 0" in text


def test_table_emoji_reflects_the_metric_guide() -> None:
    """The same value is judged against each metric's own guide."""
    text = _rendered(
        report_table(
            _report(
                _outcome("lenient", value=10, guide=100),  # a tenth of the guide
                _outcome("strict", value=10, guide=4),  # past twice it
            )
        )
    )

    assert "🦠 10" in text
    assert "💀 10" in text


def test_table_group_row_sums_the_group() -> None:
    text = _rendered(
        report_table(
            _report(
                _outcome("a", "linting", value=61, guide=100),
                _outcome("b", "linting", value=17, guide=100),
            )
        )
    )

    # 78 against a summed guide of 200 is more than a quarter of it, under half
    assert "🚧 78" in text


def test_table_stays_unchanged_when_nothing_is_grouped() -> None:
    """A groupless config must not sprout group rows."""
    text = _rendered(report_table(_report(_outcome("a"), _outcome("b"))))

    assert "Group" not in text
    assert "(ungrouped)" not in text


def test_an_errored_metric_shows_no_emoji() -> None:
    text = _rendered(report_table(_report(_failed("boom"))))

    assert "ERROR" in text
    assert "🎉" not in text  # an error is not a triumph


def test_a_group_holding_an_error_still_sums_the_rest() -> None:
    text = _rendered(
        report_table(_report(_outcome("a", "g", value=3), _failed("boom", "g")))
    )

    assert "🦠 3" in text


def test_listing_heading_carries_the_group_sum() -> None:
    text = _plain(
        run_listing(
            _report(
                _outcome("a", "typing", value=61, guide=100),
                _outcome("b", "typing", value=17, guide=100),
            )
        )
    )

    assert "## typing  🚧 78" in text


def test_listing_prints_a_metric_description() -> None:
    text = _plain(
        run_listing(_report(_outcome("a", description="Lint rules silenced inline.")))
    )

    assert "Lint rules silenced inline." in text


def test_listing_omits_the_description_line_when_unset() -> None:
    lines = run_listing(_report(_outcome("a")))

    assert not any("None" in line.plain for line in lines)


def test_listing_without_groups_still_has_no_headings() -> None:
    text = _plain(run_listing(_report(_outcome("a"), _outcome("b"))))

    assert "##" not in text


def test_diff_listing_prints_a_description() -> None:
    report = _diff_report(
        DiffOutcome(
            spec=MetricSpec(
                name="a", type="file_count", description="Files over 1k lines."
            ),
            range_names=(),
            result=DiffResult(net=1, added=1, removed=0),
            total=MetricResult(value=5),
        )
    )

    assert "Files over 1k lines." in _plain(diff_listing(report))


def test_diff_table_group_row_judges_the_standing_total_not_the_net() -> None:
    """A net of zero does not mean the group carries no debt."""
    text = _rendered(
        diff_table(
            _diff_report(
                _diff_outcome("a", "size", net=0, total=150, guide=100),
                _diff_outcome("b", "size", net=0, total=150, guide=100),
            )
        )
    )

    # 300 standing against a summed guide of 200 is half again past it
    assert "🔥 300" in text
    assert "🎉" not in text  # which the net alone would have called a triumph


def test_run_json_carries_guide_and_description() -> None:
    payload = json.loads(
        run_json(_report(_outcome("a", guide=25, description="Why this matters.")))
    )
    (entry,) = payload["metrics"]

    assert entry["guide"] == 25
    assert entry["description"] == "Why this matters."


def test_json_description_is_null_when_unset() -> None:
    payload = json.loads(run_json(_report(_outcome("a"))))

    assert payload["metrics"][0]["description"] is None


def test_json_carries_no_emoji() -> None:
    """Machine output stays machine output."""
    payload = run_json(_report(_outcome("a", value=0)))

    assert "🎉" not in payload


def test_diff_json_carries_guide_and_description() -> None:
    report = _diff_report(_diff_outcome("a", guide=7, net=1, total=2))
    payload = json.loads(diff_json(report))

    assert payload["metrics"][0]["guide"] == 7
    assert payload["metrics"][0]["description"] is None


def _verdict(*, net_total: int, judged: int, failed: bool = False) -> CheckVerdict:
    return CheckVerdict(
        policy=CheckPolicy.SUM,
        worsened=(),
        net_total=net_total,
        failed=failed,
        judged=judged,
    )


def test_a_passing_check_says_so() -> None:
    """Silence in a CI log cannot be told apart from a step that never ran."""
    line = check_success(_verdict(net_total=0, judged=12), "main")

    assert line.plain == "🎉 no new debt: 12 metrics against main"


def test_a_passing_check_reports_debt_paid_off() -> None:
    line = check_success(_verdict(net_total=-3, judged=12), "main")

    assert line.plain == "🎉 no new debt, and 3 paid off: 12 metrics against main"


def test_a_single_judged_metric_is_not_pluralised() -> None:
    line = check_success(_verdict(net_total=0, judged=1), "develop")

    assert line.plain == "🎉 no new debt: 1 metric against develop"
