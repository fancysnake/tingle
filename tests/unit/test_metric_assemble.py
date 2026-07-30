from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING

from tingle.mills.metrics.assemble import per_file_result, presence_crossings
from tingle.pacts.diff import DiffMetricContext, FileDiff, FileStatus
from tingle.pacts.metrics import MetricResult, Occurrence

if TYPE_CHECKING:
    from collections.abc import Mapping


def _context(
    files: tuple[FileDiff, ...],
    current: Mapping[str, str | None],
    *,
    base: Mapping[str, str | None],
) -> DiffMetricContext:
    return DiffMetricContext(
        files=files,
        read=lambda path: current.get(str(path)),
        read_base=lambda path: base.get(str(path)),
        params={},
    )


def _present(_path: PurePath, text: str, _side: str) -> tuple[bool, list[str]]:
    return "HIT" in text, []


# per_file_result


def test_collapses_many_hits_in_one_file_to_one() -> None:
    located = MetricResult(
        value=3,
        details={"a.py": 3},
        occurrences=(
            Occurrence(path="a.py", line=4),
            Occurrence(path="a.py", line=9),
            Occurrence(path="a.py", line=12),
        ),
    )

    result = per_file_result(located)

    assert result.value == 1
    assert [str(o) for o in result.occurrences] == ["a.py:4"]


def test_counts_each_file_once() -> None:
    located = MetricResult(
        value=4,
        details={"a.py": 3, "b.py": 1},
        occurrences=(
            Occurrence(path="a.py", line=1),
            Occurrence(path="a.py", line=2),
            Occurrence(path="a.py", line=3),
            Occurrence(path="b.py", line=7),
        ),
    )

    result = per_file_result(located)

    assert result.value == 2
    assert [str(o) for o in result.occurrences] == ["a.py:1", "b.py:7"]


def test_keeps_hit_counts_in_details() -> None:
    located = MetricResult(
        value=4,
        details={"a.py": 3, "b.py": 1},
        occurrences=(Occurrence(path="a.py", line=1), Occurrence(path="b.py", line=7)),
    )

    result = per_file_result(located)

    # details stay per-hit while the value is per-file: the report still says
    # how heavily a file is involved, so the two deliberately disagree
    assert dict(result.details) == {"a.py": 3, "b.py": 1}
    assert sum(result.details.values()) != result.value


def test_collapse_of_nothing_is_zero() -> None:
    result = per_file_result(MetricResult(value=0))

    assert result.value == 0
    assert not result.occurrences


def test_collapse_passes_warnings_through() -> None:
    located = MetricResult(value=0, warnings=("blob.bin: skipped",))

    result = per_file_result(located)

    assert result.warnings == ("blob.bin: skipped",)


def test_collapse_keeps_occurrence_without_a_line() -> None:
    located = MetricResult(value=1, occurrences=(Occurrence(path="a.py"),))

    result = per_file_result(located)

    assert result.value == 1
    assert [str(o) for o in result.occurrences] == ["a.py"]


# presence_crossings


def test_appearing_in_a_file_counts_as_added() -> None:
    file = FileDiff(path=PurePath("a.py"), status=FileStatus.MODIFIED)

    result = presence_crossings(
        _context((file,), {"a.py": "HIT\n"}, base={"a.py": "clean\n"}), present=_present
    )

    assert result.added == 1
    assert result.removed == 0
    assert result.net == 1
    assert [str(o) for o in result.added_occurrences] == ["a.py"]


def test_vanishing_from_a_file_counts_as_removed() -> None:
    file = FileDiff(path=PurePath("a.py"), status=FileStatus.MODIFIED)

    result = presence_crossings(
        _context((file,), {"a.py": "clean\n"}, base={"a.py": "HIT\n"}), present=_present
    )

    assert result.removed == 1
    assert result.net == -1
    assert [str(o) for o in result.removed_occurrences] == ["a.py"]


def test_rewriting_a_file_that_already_had_it_moves_nothing() -> None:
    file = FileDiff(
        path=PurePath("a.py"),
        status=FileStatus.MODIFIED,
        added_lines=frozenset({1, 2, 3}),
        removed_lines=frozenset({1, 2, 3}),
    )

    result = presence_crossings(
        _context((file,), {"a.py": "HIT\nHIT\nHIT\n"}, base={"a.py": "HIT\nother\n"}),
        present=_present,
    )

    assert result.net == 0
    assert result.added == 0
    assert result.removed == 0
    assert not result.details


def test_created_file_with_the_thing_counts_as_added() -> None:
    file = FileDiff(path=PurePath("new.py"), status=FileStatus.ADDED)

    result = presence_crossings(
        _context((file,), {"new.py": "HIT\n"}, base={}), present=_present
    )

    assert result.net == 1
    assert not result.warnings


def test_deleted_file_with_the_thing_counts_as_removed() -> None:
    file = FileDiff(path=PurePath("gone.py"), status=FileStatus.DELETED)

    result = presence_crossings(
        _context((file,), {}, base={"gone.py": "HIT\n"}), present=_present
    )

    assert result.net == -1
    assert not result.warnings


def test_details_carry_the_per_file_net() -> None:
    gained = FileDiff(path=PurePath("a.py"), status=FileStatus.MODIFIED)
    lost = FileDiff(path=PurePath("b.py"), status=FileStatus.MODIFIED)

    result = presence_crossings(
        _context(
            (gained, lost),
            {"a.py": "HIT\n", "b.py": "clean\n"},
            base={"a.py": "clean\n", "b.py": "HIT\n"},
        ),
        present=_present,
    )

    assert result.net == 0
    assert result.added == 1
    assert result.removed == 1
    assert dict(result.details) == {"a.py": 1, "b.py": -1}


def test_unreadable_side_warns_when_the_file_should_be_there() -> None:
    file = FileDiff(path=PurePath("a.py"), status=FileStatus.MODIFIED)

    result = presence_crossings(
        _context((file,), {"a.py": None}, base={"a.py": "HIT\n"}), present=_present
    )

    assert result.warnings == ("a.py: current side unreadable",)
    assert result.net == -1


def test_suffix_skips_files_of_other_kinds() -> None:
    file = FileDiff(path=PurePath("notes.md"), status=FileStatus.ADDED)

    result = presence_crossings(
        _context((file,), {"notes.md": "HIT\n"}, base={}),
        present=_present,
        suffix=".py",
    )

    assert result.net == 0
    assert not result.warnings


def test_side_warnings_reach_the_result() -> None:
    def warns(_path: PurePath, text: str, side: str) -> tuple[bool, list[str]]:
        return "HIT" in text, [f"{side} side is odd"]

    file = FileDiff(path=PurePath("a.py"), status=FileStatus.MODIFIED)

    result = presence_crossings(
        _context((file,), {"a.py": "HIT\n"}, base={"a.py": "HIT\n"}), present=warns
    )

    assert result.warnings == ("current side is odd", "base side is odd")
