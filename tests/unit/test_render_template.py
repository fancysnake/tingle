"""Rendering a template as the config entry it stands for."""

from __future__ import annotations

from tingle.gates.cli.render import template_toml
from tingle.pacts.config import LibraryEntry, MetricTemplate


def _rendered(template: MetricTemplate) -> list[str]:
    return template_toml(LibraryEntry(path="pack.one", template=template)).splitlines()


def test_a_full_template_renders_as_a_metrics_entry() -> None:
    lines = _rendered(
        MetricTemplate(
            type="regex_count",
            name="noqa",
            group="linting",
            description="noqa comments.",
            guide=200,
            ranges=("python", "js"),
            params={"pattern": r"#\s*noqa"},
        )
    )

    assert lines == [
        "# pack.one",
        "[[metrics]]",
        'name = "noqa"',
        'type = "regex_count"',
        'group = "linting"',
        'description = "noqa comments."',
        "guide = 200",
        'ranges = ["python", "js"]',
        r"pattern = '#\s*noqa'",
    ]


def test_unstated_fields_are_left_out() -> None:
    assert _rendered(MetricTemplate(type="line_count")) == [
        "# pack.one",
        "[[metrics]]",
        'type = "line_count"',
    ]


def test_a_backslash_gets_a_literal_string_and_a_quote_stops_it() -> None:
    """A regex is unreadable escaped twice, but a literal cannot hold `'`."""
    literal = _rendered(MetricTemplate(params={"pattern": r"\d+"}))
    basic = _rendered(MetricTemplate(params={"pattern": r"it\'s"}))

    assert literal[-1] == r"pattern = '\d+'"
    assert basic[-1] == 'pattern = "it\\\\\'s"'


def test_numbers_and_booleans_keep_their_types() -> None:
    lines = _rendered(
        MetricTemplate(params={"over_lines": 1000, "explode": True, "off": False})
    )

    assert lines[-3:] == ["over_lines = 1000", "explode = true", "off = false"]
