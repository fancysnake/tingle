from __future__ import annotations

import pytest

from tingle.mills.starter import starter_bases
from tingle.pacts.config import ToolConfigs


def test_nothing_configured_starts_on_nothing() -> None:
    assert not starter_bases(ToolConfigs(files=frozenset({"README.md"})))


def test_ruff_and_basedpyright_start_on_their_templates_and_no_others() -> None:
    found = ToolConfigs(
        files=frozenset({"pyproject.toml"}),
        sections=frozenset({"tool.ruff", "tool.basedpyright", "tool.poetry"}),
    )

    assert starter_bases(found) == (
        "tingle.builtins.ruff.noqa_comment",
        "tingle.builtins.pyright.ignore_comment",
    )


@pytest.mark.parametrize(
    "found",
    (
        pytest.param(ToolConfigs(files=frozenset({"mypy.ini"})), id="own-file"),
        pytest.param(ToolConfigs(sections=frozenset({"tool.mypy"})), id="pyproject"),
        pytest.param(ToolConfigs(sections=frozenset({"mypy"})), id="setup-cfg"),
    ),
)
def test_a_tool_is_recognised_wherever_it_keeps_its_config(found: ToolConfigs) -> None:
    assert starter_bases(found) == ("tingle.builtins.mypy.type_ignore_comment",)


def test_a_tool_found_twice_is_started_once() -> None:
    found = ToolConfigs(
        files=frozenset({".coveragerc"}),
        sections=frozenset({"tool.coverage", "coverage:run"}),
    )

    assert starter_bases(found) == ("tingle.builtins.coverage.pragma_comment",)
