from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING, Any

from tingle.mills.metrics.regex_count import regex_spread
from tingle.pacts.metrics import MetricContext

if TYPE_CHECKING:
    from collections.abc import Mapping


def _context(
    contents: Mapping[str, str | None], params: Mapping[str, Any]
) -> MetricContext:
    return MetricContext(
        files=tuple(PurePath(name) for name in contents),
        read=lambda path: contents.get(str(path)),
        exists=lambda path: str(path) in contents,
        params=params,
    )


def test_counts_a_file_once_however_many_matches() -> None:
    contents = {"a.py": "x = 1  # noqa\ny = 2  # noqa\nz = 3  # noqa\n"}

    result = regex_spread(_context(contents, {"pattern": r"#\s*noqa"}))

    assert result.value == 1
    assert [str(o) for o in result.occurrences] == ["a.py:1"]


def test_counts_each_matching_file() -> None:
    contents = {
        "a.py": "x = 1  # noqa\ny = 2  # noqa\n",
        "b.py": "clean\n",
        "c.py": "z = 3  # noqa\n",
    }

    result = regex_spread(_context(contents, {"pattern": r"#\s*noqa"}))

    assert result.value == 2
    assert [str(o) for o in result.occurrences] == ["a.py:1", "c.py:1"]


def test_occurrence_points_at_the_first_match() -> None:
    contents = {"a.py": "clean\nclean\nx = 1  # noqa\ny = 2  # noqa\n"}

    result = regex_spread(_context(contents, {"pattern": r"#\s*noqa"}))

    assert [str(o) for o in result.occurrences] == ["a.py:3"]


def test_details_keep_the_hit_count_per_file() -> None:
    contents = {"a.py": "# noqa\n# noqa\n# noqa\n", "b.py": "# noqa\n"}

    result = regex_spread(_context(contents, {"pattern": r"#\s*noqa"}))

    assert result.value == 2
    assert dict(result.details) == {"a.py": 3, "b.py": 1}


def test_no_match_is_zero() -> None:
    result = regex_spread(_context({"a.py": "clean\n"}, {"pattern": r"#\s*noqa"}))

    assert result.value == 0
    assert not result.occurrences


def test_file_whose_every_hit_is_excused_does_not_count() -> None:
    contents = {"a.py": '{"form": ANY}\n{"form": ANY}\n', "b.py": "x = ANY\n"}

    result = regex_spread(
        _context(contents, {"pattern": "ANY", "ignore_lines": [r'"form":\s*ANY']})
    )

    assert result.value == 1
    assert [str(o) for o in result.occurrences] == ["b.py:1"]


def test_file_with_one_hit_left_after_excusing_still_counts() -> None:
    contents = {"a.py": '{"form": ANY}\nx = ANY\n'}

    result = regex_spread(
        _context(contents, {"pattern": "ANY", "ignore_lines": [r'"form":\s*ANY']})
    )

    assert result.value == 1
    assert [str(o) for o in result.occurrences] == ["a.py:2"]


def test_flags_are_honoured() -> None:
    result = regex_spread(
        _context({"a.py": "# NOQA\n"}, {"pattern": "noqa", "flags": ["IGNORECASE"]})
    )

    assert result.value == 1


def test_multiline_pattern_counts_its_file_once() -> None:
    contents = {"a.py": "start\nend\nstart\nend\n"}

    result = regex_spread(
        _context(contents, {"pattern": "start\nend", "flags": ["DOTALL"]})
    )

    assert result.value == 1
    assert dict(result.details) == {"a.py": 2}


def test_unreadable_file_warns_and_does_not_count() -> None:
    contents = {"a.py": "# noqa\n", "blob.bin": None}

    result = regex_spread(_context(contents, {"pattern": r"#\s*noqa"}))

    assert result.value == 1
    assert result.warnings == ("blob.bin: skipped (binary, unreadable, or missing)",)
