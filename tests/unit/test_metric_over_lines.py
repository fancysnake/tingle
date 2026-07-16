from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING, Any

import pytest

from tingle.mills.metrics.counts import (
    file_count,
    file_count_diff,
    validate_count_params,
)
from tingle.pacts.diff import DiffMetricContext, FileDiff, FileStatus
from tingle.pacts.metrics import MetricContext

if TYPE_CHECKING:
    from collections.abc import Mapping


def _text(lines: int) -> str:
    return "".join(f"line {n}\n" for n in range(lines))


def _context(contents: Mapping[str, str], params: Mapping[str, Any]) -> MetricContext:
    return MetricContext(
        files=tuple(PurePath(name) for name in contents),
        read=lambda path: contents.get(str(path)),
        exists=lambda path: str(path) in contents,
        params=params,
    )


def _diff_context(
    current: Mapping[str, str],
    *,
    base: Mapping[str, str],
    files: tuple[FileDiff, ...],
    params: Mapping[str, Any],
) -> DiffMetricContext:
    return DiffMetricContext(
        files=files,
        read=lambda path: current.get(str(path)),
        read_base=lambda path: base.get(str(path)),
        params=params,
    )


def _modified(path: str) -> FileDiff:
    return FileDiff(path=PurePath(path), status=FileStatus.MODIFIED)


def test_without_over_lines_every_file_counts() -> None:
    ctx = _context({"a.py": _text(5000), "b.py": ""}, {})

    assert file_count(ctx).value == 2


def test_without_over_lines_no_file_is_ever_read() -> None:
    """A plain file_count opens nothing, so a binary cannot make it warn."""
    reads: list[PurePath] = []

    def spy(path: PurePath) -> str | None:
        reads.append(path)  # returns None, as an unreadable binary would

    ctx = MetricContext(
        files=(PurePath("logo.png"),), read=spy, exists=lambda _: True, params={}
    )

    result = file_count(ctx)

    assert not reads
    assert result.value == 1
    assert not result.warnings


def test_the_gate_is_strict() -> None:
    """`over_lines = 1000` means "longer than 1000", not "1000 or more"."""
    ctx = _context(
        {"exactly.py": _text(1000), "over.py": _text(1001)}, {"over_lines": 1000}
    )

    result = file_count(ctx)

    assert result.value == 1
    assert [o.path for o in result.occurrences] == ["over.py"]


def test_details_carry_how_oversized_each_file_is() -> None:
    ctx = _context({"big.py": _text(1500), "small.py": _text(10)}, {"over_lines": 1000})

    result = file_count(ctx)

    assert result.details == {"big.py": 1500}


def test_an_unreadable_file_warns_once_the_gate_is_set() -> None:
    ctx = _context({"logo.png": _text(2000)}, {"over_lines": 1000})
    ctx = MetricContext(
        files=ctx.files, read=lambda _: None, exists=ctx.exists, params=ctx.params
    )

    result = file_count(ctx)

    assert result.value == 0
    assert result.warnings


@pytest.mark.parametrize(
    "case",
    [
        # (lines before, lines now, expected added, expected removed)
        (900, 1200, 1, 0),  # grew past the gate: new debt
        (1200, 900, 0, 1),  # refactored back under it: debt paid
        (1200, 1300, 0, 0),  # already over, still over
        (100, 200, 0, 0),  # under all along
    ],
)
def test_diff_counts_crossings(case: tuple[int, int, int, int]) -> None:
    before, now, added, removed = case
    ctx = _diff_context(
        {"a.py": _text(now)},
        base={"a.py": _text(before)},
        files=(_modified("a.py"),),
        params={"over_lines": 1000},
    )

    result = file_count_diff(ctx)

    assert (result.added, result.removed) == (added, removed)
    assert result.net == added - removed


def test_diff_counts_a_file_created_over_the_gate() -> None:
    """No base side at all: creation above the gate is a crossing."""
    ctx = _diff_context(
        {"new.py": _text(1200)},
        base={},
        files=(FileDiff(path=PurePath("new.py"), status=FileStatus.ADDED),),
        params={"over_lines": 1000},
    )

    result = file_count_diff(ctx)

    assert result.added == 1
    assert result.net == 1


def test_diff_counts_an_oversized_file_deleted() -> None:
    ctx = _diff_context(
        {},
        base={"old.py": _text(1200)},
        files=(FileDiff(path=PurePath("old.py"), status=FileStatus.DELETED),),
        params={"over_lines": 1000},
    )

    result = file_count_diff(ctx)

    assert result.removed == 1
    assert result.net == -1


def test_diff_ignores_a_small_file_created() -> None:
    """Without the gate this would count; with it, only oversized files do."""
    ctx = _diff_context(
        {"new.py": _text(10)},
        base={},
        files=(FileDiff(path=PurePath("new.py"), status=FileStatus.ADDED),),
        params={"over_lines": 1000},
    )

    assert file_count_diff(ctx).net == 0


def test_diff_without_the_gate_still_counts_created_and_deleted() -> None:
    ctx = _diff_context(
        {"new.py": ""},
        base={"old.py": ""},
        files=(
            FileDiff(path=PurePath("new.py"), status=FileStatus.ADDED),
            FileDiff(path=PurePath("old.py"), status=FileStatus.DELETED),
        ),
        params={},
    )

    result = file_count_diff(ctx)

    assert (result.added, result.removed, result.net) == (1, 1, 0)


@pytest.mark.parametrize("gate", [0, -1, "1000", 1.5, True])
def test_over_lines_must_be_a_positive_integer(gate: object) -> None:
    assert validate_count_params({"over_lines": gate}) == [
        "over_lines must be a positive integer"
    ]


def test_no_over_lines_is_valid() -> None:
    assert not validate_count_params({})
