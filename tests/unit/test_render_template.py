"""Heading a template's config entry with where it came from."""

from __future__ import annotations

from typing import Any

from tingle.gates.cli.render import template_toml
from tingle.pacts.config import LibraryEntry

BODY = '[[metrics]]\nname = "noqa"\ntype = "regex_count"'


def _rendered(table: dict[str, Any], toml: str = BODY) -> list[str]:
    return template_toml(
        LibraryEntry(path="pack.one", table=table, toml=toml)
    ).splitlines()


def test_the_entry_is_headed_by_the_path_that_names_the_template() -> None:
    lines = _rendered({"name": "noqa", "type": "regex_count"})

    assert lines == [
        "# pack.one",
        "[[metrics]]",
        'name = "noqa"',
        'type = "regex_count"',
    ]


def test_a_mixin_says_what_a_reader_still_has_to_supply() -> None:
    """Pasted as it stands it is not a metric, and the config would say so."""
    lines = _rendered({"ignore_lines": ["# generated"]}, "[[metrics]]")

    assert lines[:2] == ["# pack.one", "# a mixin: add name and type of your own"]


def test_only_the_missing_half_is_asked_for() -> None:
    lines = _rendered({"type": "line_count"}, '[[metrics]]\ntype = "line_count"')

    assert lines[1] == "# a mixin: add name of your own"
