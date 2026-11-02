from __future__ import annotations

import pytest
from support import FakeProject

from tingle.mills.starter import starter_bases

MYPY = ("tingle.builtins.mypy.type_ignore_comment",)


def test_nothing_configured_starts_on_nothing() -> None:
    assert not starter_bases(FakeProject({"README.md": "", "src/mypy.ini": ""}))


def test_ruff_and_basedpyright_start_on_their_templates_and_no_others() -> None:
    project = FakeProject(
        {"pyproject.toml": "[tool.ruff]\n[tool.basedpyright]\n[tool.poetry]\n"}
    )

    assert starter_bases(project) == (
        "tingle.builtins.ruff.noqa_comment",
        "tingle.builtins.pyright.ignore_comment",
    )


@pytest.mark.parametrize(
    "contents",
    (
        pytest.param({"mypy.ini": ""}, id="own-file"),
        pytest.param({"pyproject.toml": "[tool.mypy]\n"}, id="pyproject"),
        pytest.param({"setup.cfg": "[mypy]\nstrict = True\n"}, id="setup-cfg"),
        pytest.param({"tox.ini": "[mypy]\n"}, id="tox-ini"),
    ),
)
def test_a_tool_is_recognised_wherever_it_keeps_its_config(
    contents: dict[str, str],
) -> None:
    assert starter_bases(FakeProject(contents)) == MYPY


@pytest.mark.parametrize(
    ("section", "expected"),
    (
        pytest.param(
            "pylint.messages control",
            ("tingle.builtins.pylint.disable_comment",),
            id="dotted",
        ),
        pytest.param(
            "coverage:report", ("tingle.builtins.coverage.pragma_comment",), id="colon"
        ),
        pytest.param(
            "tool:pytest",
            ("tingle.builtins.pytest.skip_marks", "tingle.builtins.pytest.xfail_marks"),
            id="tool-prefix",
        ),
    ),
)
def test_an_ini_section_counts_under_the_tool_it_is_named_for(
    section: str, expected: tuple[str, ...]
) -> None:
    project = FakeProject({"setup.cfg": f"[{section}]\nkey = value\n"})

    assert starter_bases(project) == expected


def test_a_tool_found_twice_is_started_once() -> None:
    project = FakeProject(
        {
            ".coveragerc": "",
            "pyproject.toml": "[tool.coverage.run]\n",
            "tox.ini": "[coverage:run]\n",
        }
    )

    assert starter_bases(project) == ("tingle.builtins.coverage.pragma_comment",)


def test_pyright_and_basedpyright_share_one_metric() -> None:
    project = FakeProject({"pyproject.toml": "[tool.pyright]\n[tool.basedpyright]\n"})

    assert starter_bases(project) == ("tingle.builtins.pyright.ignore_comment",)


@pytest.mark.parametrize(
    "contents",
    (
        pytest.param({"pyproject.toml": "[tool.mypy\n"}, id="toml"),
        pytest.param({"setup.cfg": "no section header\n"}, id="no-header"),
        pytest.param({"setup.cfg": "[mypy]\nstrict\n"}, id="parsing-error"),
        pytest.param({"setup.cfg": "[mypy]\n[mypy]\n"}, id="duplicate-section"),
    ),
)
def test_a_file_that_does_not_parse_names_no_tool(contents: dict[str, str]) -> None:
    assert not starter_bases(FakeProject(contents))
