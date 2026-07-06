from __future__ import annotations

from pathlib import PurePath

from tingle.mills.ranges import resolve
from tingle.pacts.config import RangeSpec
from tingle.specs.config import IMPLICIT_RANGE_INCLUDE, IMPLICIT_RANGE_NAME


def _paths(*names: str) -> list[PurePath]:
    return [PurePath(name) for name in names]


def test_include_globs_match_nested_paths() -> None:
    spec = RangeSpec(name="python", include=("src/**/*.py",))
    files = _paths("src/a.py", "src/deep/b.py", "src/c.txt", "other/d.py")

    assert resolve(files, [spec]) == (
        PurePath("src/a.py"),
        PurePath("src/deep/b.py"),
    )


def test_exclude_globs_remove_matches() -> None:
    spec = RangeSpec(
        name="python", include=("src/**/*.py",), exclude=("src/gen/**",)
    )
    files = _paths("src/a.py", "src/gen/b.py")

    assert resolve(files, [spec]) == (PurePath("src/a.py"),)


def test_union_of_overlapping_ranges_is_deduped_and_sorted() -> None:
    python = RangeSpec(name="python", include=("**/*.py",))
    src = RangeSpec(name="src", include=("src/**",))
    files = _paths("src/a.py", "src/b.txt", "top.py")

    assert resolve(files, [python, src]) == (
        PurePath("src/a.py"),
        PurePath("src/b.txt"),
        PurePath("top.py"),
    )


def test_default_excludes_apply_to_every_range() -> None:
    spec = RangeSpec(name=IMPLICIT_RANGE_NAME, include=IMPLICIT_RANGE_INCLUDE)
    files = _paths(
        "src/a.py",
        ".git/config",
        ".venv/lib/site.py",
        "pkg/__pycache__/a.cpython-314.pyc",
        "node_modules/x/index.js",
        "dist/tingle-0.1.0.tar.gz",
    )

    assert resolve(files, [spec]) == (PurePath("src/a.py"),)


def test_no_matches_returns_empty() -> None:
    spec = RangeSpec(name="python", include=("**/*.py",))

    assert resolve(_paths("readme.md"), [spec]) == ()
