from __future__ import annotations

from pathlib import PurePath

from tingle.mills.ranges import ResolvedRanges, resolve
from tingle.pacts.config import RangeSpec
from tingle.specs.config import IMPLICIT_RANGE_INCLUDE, IMPLICIT_RANGE_NAME


def _paths(*names: str) -> list[PurePath]:
    return [PurePath(name) for name in names]


def test_include_globs_match_nested_paths() -> None:
    spec = RangeSpec(name="python", include=("src/**/*.py",))
    files = _paths("src/a.py", "src/deep/b.py", "src/c.txt", "other/d.py")

    assert resolve(files, [spec]) == (PurePath("src/a.py"), PurePath("src/deep/b.py"))


def test_exclude_globs_remove_matches() -> None:
    spec = RangeSpec(name="python", include=("src/**/*.py",), exclude=("src/gen/**",))
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

    assert not resolve(_paths("readme.md"), [spec])


def test_an_anchored_default_exclude_spares_the_same_name_nested() -> None:
    """`.venv/**` is the project's own venv, not every directory so named.

    The tree walk prunes on these names, so what the glob does and what
    the walk skips have to agree at every depth or a run measures files
    it never read.
    """
    walked = (
        PurePath(".venv/lib/v.py"),
        PurePath("sub/.venv/lib/n.py"),
        PurePath("__pycache__/r.py"),
        PurePath("sub/__pycache__/n.py"),
        PurePath("src/a.py"),
    )

    resolved = resolve(walked, [RangeSpec(name="python", include=("**/*.py",))])

    assert resolved == (PurePath("src/a.py"), PurePath("sub/.venv/lib/n.py"))


def test_a_range_set_is_resolved_once_however_many_ask() -> None:
    """The second ask gets the first answer back, not an equal one."""
    ranges = ResolvedRanges(tuple(_paths("a.py", "b.py", "notes.md")))
    spec = RangeSpec(name="python", include=("**/*.py",))

    first = ranges.files(("python",), [spec])
    second = ranges.files(("python",), [spec])

    assert first == (PurePath("a.py"), PurePath("b.py"))
    assert first is second


def test_different_range_sets_are_resolved_separately() -> None:
    ranges = ResolvedRanges(tuple(_paths("a.py", "notes.md")))

    python = ranges.files(("python",), [RangeSpec(name="python", include=("**/*.py",))])
    docs = ranges.files(("docs",), [RangeSpec(name="docs", include=("**/*.md",))])

    assert python == (PurePath("a.py"),)
    assert docs == (PurePath("notes.md"),)
