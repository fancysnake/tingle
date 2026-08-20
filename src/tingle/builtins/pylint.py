"""Templates for pylint: checks silenced inline, in TOML, or in an rcfile."""

from __future__ import annotations

from tingle.pacts.config import MetricTemplate

__all__ = ["disable_comment", "pyproject_disables", "rcfile_disables"]

disable_comment = MetricTemplate(
    type="regex_count",
    name="pylint-comment",
    group="linting",
    description="`# pylint:` comments that silence a check inline.",
    params={"pattern": r"#\s*pylint:"},
)

pyproject_disables = MetricTemplate(
    type="toml_list_length",
    name="pylint-pyproject-disables",
    group="linting",
    description="Pylint checks disabled project-wide in `pyproject.toml`.",
    params={"key": "tool.pylint.messages control.disable"},
)

rcfile_disables = MetricTemplate(
    type="ini_list_length",
    name="pylint-rcfile-disables",
    group="linting",
    description="Pylint checks disabled project-wide in `.pylintrc`.",
    params={"file": ".pylintrc", "section": "MESSAGES CONTROL", "option": "disable"},
)
