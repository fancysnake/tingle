from __future__ import annotations

from pathlib import Path

from tingle.gates.cli.render import check_annotations, check_markdown
from tingle.mills.display import sections
from tingle.pacts.check import CheckVerdict
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
        failed=True,
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
