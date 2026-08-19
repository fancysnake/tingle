"""Fixtures shared by every integration test.

`isolated_git` lives here rather than beside the tests that build repos
because two suites need it -- the CLI gate's and the git link's -- and a
copy in each is a copy that can drift. The template packs are here for the
same reason, and because a test asking for `pack: str` must not shadow a
fixture function of that name in its own module.
"""

from __future__ import annotations

import sys
import textwrap
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

#: A template package the way somebody else would write one: a module that
#: states what it publishes, and things that are not templates at all.
PACK = textwrap.dedent("""
    from tingle.pacts.config import MetricTemplate

    __all__ = ["noqa"]

    noqa = MetricTemplate(type="regex_count", name="noqa", params={"pattern": "x"})
    undeclared = MetricTemplate(type="regex_count", name="undeclared")
    _private = MetricTemplate(type="regex_count", name="hidden")
    NOT_A_TEMPLATE = "just a string"
    """)

#: The same pack, one subpackage deeper: reachable, and so listable too.
NESTED = textwrap.dedent("""
    from tingle.pacts.config import MetricTemplate

    inner = MetricTemplate(type="regex_count", name="inner", params={"pattern": "y"})
    """)

#: A pack that declares a real template and a bad one, so listing it has
#: both something to show and something to complain about.
BROKEN_PACK = textwrap.dedent("""
    from tingle.pacts.config import MetricTemplate

    usable = MetricTemplate(type="regex_count", name="usable", params={"pattern": "x"})
    wrong_type = MetricTemplate(type="no_such_type", name="wrong")
    """)


def _installed(
    tmp_path: Path, name: str, *, body: str, nested: str = ""
) -> Iterator[str]:
    package = tmp_path / name
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "tools.py").write_text(body, encoding="utf-8")
    if nested:
        deeper = package / "deeper"
        deeper.mkdir()
        (deeper / "__init__.py").write_text("", encoding="utf-8")
        (deeper / "extra.py").write_text(nested, encoding="utf-8")
    yield name
    for loaded in [key for key in sys.modules if key.startswith(name)]:
        del sys.modules[loaded]


@pytest.fixture
def pack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Write a throwaway template package and put it on the import path."""
    monkeypatch.syspath_prepend(str(tmp_path))
    yield from _installed(tmp_path, "demo_pack", body=PACK, nested=NESTED)


@pytest.fixture
def broken_pack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Write a template package whose templates do not verify."""
    monkeypatch.syspath_prepend(str(tmp_path))
    yield from _installed(tmp_path, "broken_templates", body=BROKEN_PACK)


@pytest.fixture(autouse=True)
def isolated_git(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep git off the developer's own config and out of enclosing repos."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", "/dev/null")
    monkeypatch.setenv("GIT_AUTHOR_NAME", "tingle-tests")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "tests@tingle.invalid")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "tingle-tests")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "tests@tingle.invalid")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
