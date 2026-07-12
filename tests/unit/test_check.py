from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tingle.mills.check import judge
from tingle.pacts.config import CheckPolicy, CheckSpec, MetricSpec
from tingle.pacts.diff import DiffOutcome, DiffReport, DiffResult

if TYPE_CHECKING:
    from tingle.pacts.check import CheckVerdict

ROOT = Path("/proj")


def _outcome(name: str, net: int | None, *, error: str | None = None) -> DiffOutcome:
    result = None if net is None else DiffResult(net=net)
    return DiffOutcome(
        spec=MetricSpec(name=name, type="regex_count"),
        range_names=("python",),
        result=result,
        error=error,
    )


def _report(*outcomes: DiffOutcome) -> DiffReport:
    return DiffReport(
        root=ROOT,
        source=ROOT / "tingle.toml",
        base_ref="main",
        merge_base="abc123",
        outcomes=outcomes,
    )


def _judge(
    *outcomes: DiffOutcome, policy: CheckPolicy, ignore: tuple[str, ...] = ()
) -> CheckVerdict:
    return judge(_report(*outcomes), CheckSpec(policy=policy, ignore=ignore))


def test_sum_passes_when_a_gain_offsets_a_loss() -> None:
    verdict = _judge(
        _outcome("noqa", 2), _outcome("type-ignores", -3), policy=CheckPolicy.SUM
    )

    assert verdict.net_total == -1
    assert not verdict.failed


def test_sum_fails_when_the_total_grows() -> None:
    verdict = _judge(
        _outcome("noqa", 3), _outcome("type-ignores", -1), policy=CheckPolicy.SUM
    )

    assert verdict.net_total == 2
    assert verdict.failed


def test_sum_passes_on_a_net_zero_trade() -> None:
    verdict = _judge(
        _outcome("noqa", 2), _outcome("type-ignores", -2), policy=CheckPolicy.SUM
    )

    assert verdict.net_total == 0
    assert not verdict.failed


def test_any_fails_on_the_trade_that_sum_allows() -> None:
    outcomes = (_outcome("noqa", 2), _outcome("type-ignores", -3))

    assert not _judge(*outcomes, policy=CheckPolicy.SUM).failed
    assert _judge(*outcomes, policy=CheckPolicy.ANY).failed


def test_any_passes_when_nothing_grew() -> None:
    verdict = _judge(
        _outcome("noqa", 0), _outcome("type-ignores", -3), policy=CheckPolicy.ANY
    )

    assert not verdict.failed
    assert verdict.worsened == ()


def test_worsened_lists_every_grown_metric_whatever_the_policy() -> None:
    verdict = _judge(
        _outcome("noqa", 1), _outcome("type-ignores", -9), policy=CheckPolicy.SUM
    )

    assert not verdict.failed
    assert [outcome.spec.name for outcome in verdict.worsened] == ["noqa"]


def test_ignored_metric_neither_fails_nor_counts() -> None:
    verdict = _judge(
        _outcome("loc", 500),
        _outcome("noqa", -1),
        policy=CheckPolicy.ANY,
        ignore=("loc",),
    )

    assert verdict.net_total == -1
    assert verdict.worsened == ()
    assert not verdict.failed


def test_errored_metric_is_not_evidence_either_way() -> None:
    verdict = _judge(
        _outcome("broken", None, error="boom"),
        _outcome("noqa", -1),
        policy=CheckPolicy.ANY,
    )

    assert verdict.net_total == -1
    assert not verdict.failed


def test_empty_report_passes() -> None:
    verdict = _judge(policy=CheckPolicy.SUM)

    assert verdict.net_total == 0
    assert not verdict.failed
    assert verdict.worsened == ()
