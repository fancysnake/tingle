from __future__ import annotations

from pathlib import Path, PurePath

from tingle.gates.cli.render import check_annotations, check_markdown, check_reason
from tingle.mills.display import sections
from tingle.pacts.check import CheckVerdict, Loosening, StrictVerdict
from tingle.pacts.config import CheckPolicy, MetricSpec
from tingle.pacts.diff import DiffOutcome, DiffReport, DiffResult
from tingle.pacts.metrics import MetricResult, Occurrence


def _worsened(name: str, *added: Occurrence) -> DiffOutcome:
    return DiffOutcome(
        spec=MetricSpec(name=name, type="regex_count"),
        range_names=(),
        emoji="",
        result=DiffResult(
            net=len(added), added=len(added), removed=0, added_occurrences=added
        ),
        total=MetricResult(value=len(added)),
    )


def _judged(
    outcome: DiffOutcome, root: str = "/repo"
) -> tuple[DiffReport, CheckVerdict]:
    report = DiffReport(
        root=Path(root),
        source=Path(root) / "tingle.toml",
        base_ref="main",
        merge_base="abc123",
        sections=sections((outcome,)),
    )
    verdict = CheckVerdict(
        policy=CheckPolicy.SUM,
        worsened=(outcome,),
        net_total=outcome.result.net if outcome.result else 0,
        over_policy=True,
        judged=1,
    )
    return report, verdict


def test_annotation_escapes_what_would_end_a_property_or_the_message() -> None:
    outcome = _worsened(
        "odd,name",
        Occurrence("a:b,c%.py", line=3),
        Occurrence("x.toml", note="50%\nE1"),
    )

    commands = check_annotations(*_judged(outcome), cwd=Path("/repo"))

    assert commands == [
        "::error file=a%3Ab%2Cc%25.py,line=3,title=tingle%3A odd%2Cname::odd,name +1",
        "::error file=x.toml,title=tingle%3A odd%2Cname::odd,name +1: 50%25%0AE1",
    ]


def test_annotation_paths_are_relative_to_the_working_directory() -> None:
    outcome = _worsened("noqa", Occurrence("src/a.py", line=1))

    commands = check_annotations(*_judged(outcome, root="/ws/sub"), cwd=Path("/ws"))

    assert commands[0].startswith("::error file=sub/src/a.py,line=1,")


def test_markdown_cuts_a_long_addition_list() -> None:
    outcome = _worsened("noqa", *(Occurrence("a.py", line=n) for n in range(1, 206)))

    markdown = check_markdown(*_judged(outcome))

    assert "<summary>Added (205)</summary>" in markdown
    assert "- `noqa` `a.py:200`" in markdown
    assert "a.py:201" not in markdown
    assert "- …and 5 more" in markdown


def _strict_verdict(*, failed: bool = False) -> CheckVerdict:
    return CheckVerdict(
        policy=CheckPolicy.SUM,
        worsened=(),
        net_total=2 if failed else 0,
        over_policy=failed,
        strict=StrictVerdict(
            loosened=(Loosening("noqa", "5 to 3"),), alongside=(PurePath("a.py"),)
        ),
    )


def test_the_reason_names_loosening_alone() -> None:
    assert check_reason(_strict_verdict()) == (
        "check failed: noqa loosened alongside 1 other changed file"
    )


def test_the_reason_names_debt_and_loosening_together() -> None:
    assert check_reason(_strict_verdict(failed=True)) == (
        "check failed: metrics grew by a net +2 (policy: sum);"
        " noqa loosened alongside 1 other changed file"
    )


def test_markdown_and_annotations_carry_the_loosening() -> None:
    report, _ = _judged(_worsened("noqa"))
    verdict = _strict_verdict()

    assert "- `noqa`: 5 to 3" in check_markdown(report, verdict)
    assert "- changed alongside: `a.py`" in check_markdown(report, verdict)
    assert check_annotations(report, verdict, cwd=Path("/repo")) == [
        (
            "::error title=tingle%3A strict::check failed: noqa loosened"
            " alongside 1 other changed file"
        )
    ]


def test_additions_the_policy_allowed_stay_warnings_when_strict_rejects() -> None:
    outcome = _worsened("noqa", Occurrence("a.py", line=1))
    report, _ = _judged(outcome)
    verdict = CheckVerdict(
        policy=CheckPolicy.SUM,
        worsened=(outcome,),
        net_total=1,
        over_policy=False,
        strict=StrictVerdict(
            loosened=(Loosening("noqa", "5 to 3"),), alongside=(PurePath("a.py"),)
        ),
    )

    commands = check_annotations(report, verdict, cwd=Path("/repo"))

    assert commands[0].startswith("::warning file=a.py,line=1,")
    assert commands[1].startswith("::error title=tingle%3A strict::")


def test_the_strict_annotation_leaves_the_policy_failure_out() -> None:
    report, _ = _judged(_worsened("noqa"))

    commands = check_annotations(
        report, _strict_verdict(failed=True), cwd=Path("/repo")
    )

    assert commands == [
        (
            "::error title=tingle%3A strict::check failed: noqa loosened"
            " alongside 1 other changed file"
        )
    ]


def test_a_skipped_strict_mode_warns() -> None:
    report, _ = _judged(_worsened("noqa"))
    verdict = CheckVerdict(
        policy=CheckPolicy.SUM,
        worsened=(),
        net_total=0,
        over_policy=False,
        strict=StrictVerdict(skipped="strict mode skipped: why"),
    )

    assert "strict mode skipped: why" in check_markdown(report, verdict)
    assert check_annotations(report, verdict, cwd=Path("/repo")) == [
        "::warning title=tingle%3A strict::strict mode skipped: why"
    ]
