from __future__ import annotations

from tingle.specs.ranges import DEFAULT_EXCLUDES, UNREACHABLE_DIRS


def test_the_excludes_are_derived_from_the_directories() -> None:
    """One fact, two readings: the globs must still say what they said."""
    assert DEFAULT_EXCLUDES == (
        ".git/**",
        ".venv/**",
        "**/__pycache__/**",
        "node_modules/**",
        "dist/**",
        ".tox/**",
        ".mise/**",
    )


def test_every_unreachable_directory_has_an_exclude() -> None:
    assert len(DEFAULT_EXCLUDES) == len(UNREACHABLE_DIRS)
